from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from app.api.cases import Action
from app.modules.audit import service as audit
from app.modules.audit.models import audit_events
from app.modules.bookings.models import bookings
from app.modules.notifications.models import notifications
from app.modules.ops import service
from app.modules.ops.models import case_actions, cases
from app.modules.payments import service as payment_service
from app.modules.payments.gateway import Observation
from app.modules.payments.models import payments


@pytest.fixture
def issue(candidate):
    client, actor, slot, offer, body = candidate
    booking = client.post("/bookings", json=body).json()
    case = client.post("/ops/cases", json={"booking_id": booking["id"]}).json()
    return client, actor, UUID(booking["id"]), case


def action(kind, version, **fields):
    value = dict(action=kind, version=version, idempotency_key=str(uuid4()))
    if kind != "assign":
        value.update(evidence_id=str(uuid4()), note="Synthetic manual action evidence")
    return value | fields


def send(client, case, body):
    return client.post(f"/ops/cases/{case['id']}/actions", json=body)


def reject(client, booking):
    assert client.post(f"/ops/bookings/{booking}/reject", json={}).status_code == 200


def test_failed_booking_end_to_end(issue, db):
    client, actor, booking, case = issue
    reject(client, booking)
    assigned = send(client, case, action("assign", 1, assigned_to=str(actor)))
    assert assigned.status_code == 200
    assert send(client, case, action("escalate", 2)).json()["state"] == "ESCALATED"
    assert client.get("/ops/queues/escalations").json()[0]["id"] == case["id"]
    assert send(client, case, action("record", 3)).status_code == 200
    body = action("resolve", 4)
    response = send(client, case, body)
    assert response.status_code == 200
    assert response.json()["state"] == "RESOLVED"
    assert response.json()["payment"] is None
    assert not response.json()["financial_follow_up_required"]
    assert response.json()["resolution_evidence_id"] == body["evidence_id"]
    assert send(client, case, body).json()["version"] == 5
    assert send(client, case, action("record", 5)).status_code == 409
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(case_actions)) == 4
        assert (
            conn.scalar(
                select(func.count())
                .select_from(audit_events)
                .where(audit_events.c.resource_id == UUID(case["id"]))
            )
            == 5
        )
        assert (
            conn.scalar(select(bookings.c.state).where(bookings.c.id == booking))
            == "FAILED"
        )
    assert len(client.get(f"/ops/cases/{case['id']}/actions").json()) == 4
    assert send(client, case, action("reopen", 5)).json()["state"] == "OPEN"


@pytest.mark.parametrize("state", ["PENDING", "SUCCEEDED", "FAILED"])
def test_financial_outcomes_are_not_invented(issue, db, state):
    client, actor, booking, case = issue
    payment, _ = payment_service.prepare(db, actor, booking, uuid4())
    if state != "PENDING":
        payment_service.apply(
            db,
            Observation(
                payment_id=payment["id"], amount_paise=100, currency="INR", state=state
            ),
        )
    reject(client, booking)
    send(client, case, action("assign", 1, assigned_to=str(actor)))
    response = send(client, case, action("resolve", 2))
    assert response.status_code == (200 if state == "FAILED" else 409)
    view = client.get(f"/ops/cases/{case['id']}").json()
    assert view["payment"]["state"] == state
    assert view["financial_follow_up_required"] == (state != "FAILED")
    if state != "FAILED":
        assert send(client, case, action("record", 2)).json()["state"] == "OPEN"
        queue = client.get("/ops/queues/payment-review").json()
        assert queue[0]["id"] == str(payment["id"])
        assert queue[0]["review_reason"] == (
            "BOOKING_FAILED" if state == "SUCCEEDED" else "GATEWAY_UNKNOWN"
        )
    with db.connect() as conn:
        assert conn.scalar(select(payments.c.state)) == state


def test_late_payment_success_survives_closed_case(issue, db):
    client, actor, booking, case = issue
    payment, _ = payment_service.prepare(db, actor, booking, uuid4())
    observation = dict(payment_id=payment["id"], amount_paise=100, currency="INR")
    payment_service.apply(db, Observation(**observation, state="FAILED"))
    reject(client, booking)
    send(client, case, action("assign", 1, assigned_to=str(actor)))
    assert send(client, case, action("resolve", 2)).status_code == 200
    payment_service.apply(db, Observation(**observation, state="SUCCEEDED"))
    view = client.get(f"/ops/cases/{case['id']}").json()
    assert view["financial_follow_up_required"]
    assert client.get("/ops/queues/payment-review").json()[0]["id"] == str(
        payment["id"]
    )
    assert send(client, case, action("reopen", 3)).status_code == 200


def test_resolution_prerequisites(issue, db):
    client, actor, booking, case = issue
    assert send(client, case, action("resolve", 1)).status_code == 409
    assert (
        send(client, case, action("assign", 1, assigned_to=str(uuid4()))).status_code
        == 409
    )
    send(client, case, action("assign", 1, assigned_to=str(actor)))
    assert send(client, case, action("resolve", 2)).status_code == 409
    reject(client, booking)
    with db.begin() as conn:
        conn.execute(
            update(notifications)
            .where(notifications.c.booking_id == booking)
            .values(state="FAILED", attempts=3)
        )
    assert send(client, case, action("resolve", 2)).status_code == 409
    assert client.get("/ops/queues/failed-notifications").json()[0][
        "booking_id"
    ] == str(booking)
    bad = action("resolve", 2, evidence_id=None)
    assert send(client, case, bad).status_code == 422
    assert send(client, case, action("record", True)).status_code == 422


@pytest.mark.parametrize("authenticated", [False, True])
def test_permissions(issue, login, authenticated):
    client, actor, booking, case = issue
    client.cookies.clear()
    if authenticated:
        login("customer2@example.com")
    expected = 403 if authenticated else 401
    for path in [
        "/ops/queues/pending-confirmations",
        "/ops/queues/failed-bookings",
        "/ops/queues/payment-review",
        "/ops/queues/failed-notifications",
        "/ops/queues/escalations",
        f"/ops/cases/{case['id']}",
        f"/ops/cases/{case['id']}/actions",
    ]:
        assert client.get(path).status_code == expected
    assert (
        client.post("/ops/cases", json={"booking_id": str(booking)}).status_code
        == expected
    )
    assert send(client, case, action("resolve", 1)).status_code == expected


def test_duplicate_creation_and_concurrent_updates(issue, db):
    client, actor, booking, case = issue
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.create(db, actor, booking), range(2)))
    assert {r["id"] for r in results} == {UUID(case["id"])}
    bodies = [Action(**action("record", 1)), Action(**action("escalate", 1))]

    def attempt(body):
        try:
            service.act(db, actor, UUID(case["id"]), body)
            return "ok"
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, bodies)) == ["conflict", "ok"]
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(cases)) == 1
        assert conn.scalar(select(func.count()).select_from(case_actions)) == 1


def test_concurrent_identical_action_and_conflicting_reuse(issue, db):
    client, actor, booking, case = issue
    body = Action(**action("record", 1))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: service.act(db, actor, UUID(case["id"]), body), range(2))
        )
    assert [r["version"] for r in results] == [2, 2]
    changed = body.model_copy(update={"note": "Different action"})
    with pytest.raises(ValueError):
        service.act(db, actor, UUID(case["id"]), changed)


def test_atomic_audit_failure(issue, db, monkeypatch):
    client, actor, booking, case = issue

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(audit, "record", fail)
    with pytest.raises(RuntimeError):
        service.act(db, actor, UUID(case["id"]), Action(**action("record", 1)))
    with db.connect() as conn:
        assert conn.scalar(select(cases.c.version)) == 1
        assert conn.scalar(select(func.count()).select_from(case_actions)) == 0


def test_action_evidence_cannot_be_overwritten(issue, db):
    client, actor, booking, case = issue
    send(client, case, action("record", 1))
    with pytest.raises(DBAPIError), db.begin() as conn:
        conn.execute(update(case_actions).values(request={}))


def test_queues_expiry_pagination_and_missing_resources(issue, db):
    client, actor, booking, case = issue
    assert client.get("/ops/queues/pending-confirmations").json()[0]["id"] == str(
        booking
    )
    with db.begin() as conn:
        conn.execute(
            update(bookings)
            .where(bookings.c.id == booking)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    assert client.get("/ops/queues/pending-confirmations").json() == []
    rows = client.get("/ops/queues/failed-bookings?limit=1").json()
    assert rows[0]["state"] == "FAILED"
    assert client.get(f"/ops/queues/failed-bookings?after={booking}").json() == []
    assert client.get("/ops/queues/failed-bookings?limit=101").status_code == 422
    assert client.get("/ops/queues/invented").status_code == 422
    assert client.get(f"/ops/cases/{uuid4()}").status_code == 404
    assert (
        client.post("/ops/cases", json={"booking_id": str(uuid4())}).status_code == 404
    )


def test_concurrent_first_case_creation(candidate, db):
    client, actor, slot, offer, body = candidate
    booking = UUID(client.post("/bookings", json=body).json()["id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.create(db, actor, booking), range(2)))
    assert results[0]["id"] == results[1]["id"]
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(cases)) == 1
        assert (
            conn.scalar(
                select(func.count())
                .select_from(audit_events)
                .where(audit_events.c.resource_id == results[0]["id"])
            )
            == 1
        )


def test_creation_rolls_back_if_audit_fails(candidate, db, monkeypatch):
    client, actor, slot, offer, body = candidate
    booking = UUID(client.post("/bookings", json=body).json()["id"])

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(audit, "record", fail)
    with pytest.raises(RuntimeError):
        service.create(db, actor, booking)
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(cases)) == 0
