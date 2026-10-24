from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import DBAPIError

from app.api.bookings import Create
from app.modules.audit import service as audit
from app.modules.audit.models import audit_events
from app.modules.bookings import service
from app.modules.bookings.models import booking_components, bookings
from app.modules.identity.models import users
from app.modules.inventory.models import holds, inventory_slots


def create(candidate):
    client, _, _, _, body = candidate
    response = client.post("/bookings", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_confirmation_requires_evidence_and_is_idempotent(candidate, db):
    client, _, slot, _, body = candidate
    booking = create(candidate)
    assert booking["state"] == "VENDOR_CONFIRMATION_PENDING"
    path = f"/ops/bookings/{booking['id']}/confirm"
    assert client.post(path, json={}).status_code == 422
    evidence = {"vendor_confirmation_id": str(uuid4())}
    response = client.post(path, json=evidence)
    assert response.status_code == 200, response.text
    assert response.json()["state"] == response.json()["component_state"] == "CONFIRMED"
    assert "payment_status" not in response.json()
    assert client.post(path, json=evidence).status_code == 200
    assert (
        client.post(path, json={"vendor_confirmation_id": str(uuid4())}).status_code
        == 409
    )
    assert (
        client.post(f"/ops/bookings/{booking['id']}/reject", json={}).status_code == 409
    )
    with db.connect() as conn:
        item = conn.execute(select(booking_components)).mappings().one()
        assert str(item["vendor_confirmation_id"]) == evidence["vendor_confirmation_id"]
        assert item["confirmed_by"] is not None and item["confirmed_at"] is not None
        assert (
            conn.scalar(
                select(func.count())
                .select_from(audit_events)
                .where(
                    audit_events.c.resource_id == UUID(booking["id"]),
                    audit_events.c.action == "confirmed",
                )
            )
            == 1
        )
    with db.begin() as conn:
        conn.execute(update(holds).values(expires_at=func.now() - timedelta(seconds=1)))
    assert (
        client.get(f"/ops/inventory/slots/{slot['id']}").json()["available_quantity"]
        == 0
    )
    assert (
        client.post(
            "/bookings", json={**body, "idempotency_key": str(uuid4())}
        ).status_code
        == 409
    )
    assert service.expire(db) == 0


def test_concurrent_retries_and_conflicts(candidate, db):
    client, _, _, _, body = candidate
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(
            pool.map(lambda _: client.post("/bookings", json=body), range(6))
        )
    assert all(r.status_code == 201 for r in responses)
    assert len({r.json()["id"] for r in responses}) == 1
    assert (
        client.post("/bookings", json={**body, "budget_paise": 999}).status_code == 409
    )
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(bookings)) == 1
        assert conn.scalar(select(func.count()).select_from(holds)) == 1


def test_different_customers_race_for_capacity(candidate, db):
    _, _, _, _, body = candidate
    actors = [uuid4() for _ in range(6)]
    with db.begin() as conn:
        conn.execute(
            insert(users),
            [
                dict(id=actor, email=f"race{i}@example.com")
                for i, actor in enumerate(actors)
            ],
        )

    def attempt(actor):
        try:
            return service.create(db, actor, Create.model_validate(body))
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, actors))
    assert sum(r is not None for r in results) == 1


@pytest.mark.parametrize(
    "invalid",
    [
        "price",
        "requirements",
        "unverified",
        "stale",
        "expired_request",
        "budget",
        "extra",
    ],
)
def test_creation_revalidates(candidate, db, invalid):
    client, _, slot, offer, body = candidate
    if invalid == "price":
        offer["unit_price_paise"] = 101
        assert (
            client.put(
                f"/ops/inventory/slots/{slot['id']}/offer", json=offer
            ).status_code
            == 200
        )
    elif invalid == "requirements":
        body["requirements"] = [
            dict(key="missing", strength="hard", operator="eq", expected=True)
        ]
    elif invalid == "unverified":
        with db.begin() as conn:
            conn.execute(update(inventory_slots).values(state="UNKNOWN"))
    elif invalid == "stale":
        with db.begin() as conn:
            conn.execute(
                update(inventory_slots).values(
                    verified_at=func.now() - timedelta(minutes=2),
                    verified_until=func.now() - timedelta(minutes=1),
                )
            )
    elif invalid == "expired_request":
        body["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    elif invalid == "budget":
        body["budget_paise"] = 99
    else:
        body["state"] = "CONFIRMED"
    assert client.post("/bookings", json=body).status_code == (
        422 if invalid == "extra" else 409
    )
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(bookings)) == 0
        assert conn.scalar(select(func.count()).select_from(holds)) == 0


def test_customer_ownership_and_ops_permissions(candidate, login):
    client, _, _, _, body = candidate
    login("owner@example.com")
    booking = create(candidate)
    assert client.get(f"/bookings/{booking['id']}").status_code == 200
    assert (
        client.post(
            f"/ops/bookings/{booking['id']}/confirm",
            json={"vendor_confirmation_id": str(uuid4())},
        ).status_code
        == 403
    )
    assert (
        client.post(f"/ops/bookings/{booking['id']}/reject", json={}).status_code == 403
    )
    login("other@example.com")
    assert client.get(f"/bookings/{booking['id']}").status_code == 404
    client.cookies.clear()
    assert client.get(f"/bookings/{booking['id']}").status_code == 401
    assert client.post("/bookings", json=body).status_code == 401


def make_expired(db):
    with db.begin() as conn:
        conn.execute(
            update(bookings).values(expires_at=func.now() - timedelta(seconds=1))
        )
        conn.execute(update(holds).values(expires_at=func.now() - timedelta(seconds=1)))


def test_expiry_job_is_idempotent_and_releases_capacity(candidate, db):
    client, _, slot, _, body = candidate
    booking = create(candidate)
    make_expired(db)
    assert client.get(f"/bookings/{booking['id']}").json()["state"] == "FAILED"
    assert service.expire(db) == 1
    assert service.expire(db) == 0
    assert (
        client.post(
            f"/ops/bookings/{booking['id']}/confirm",
            json={"vendor_confirmation_id": str(uuid4())},
        ).status_code
        == 409
    )
    assert (
        client.get(f"/ops/inventory/slots/{slot['id']}").json()["available_quantity"]
        == 1
    )
    assert client.post("/bookings", json=body).json()["state"] == "FAILED"


def test_late_confirmation_persists_failure(candidate, db):
    client, _, _, _, _ = candidate
    booking = create(candidate)
    make_expired(db)
    assert (
        client.post(
            f"/ops/bookings/{booking['id']}/confirm",
            json={"vendor_confirmation_id": str(uuid4())},
        ).status_code
        == 409
    )
    with db.connect() as conn:
        assert conn.scalar(select(bookings.c.state)) == "FAILED"
        assert conn.scalar(select(holds.c.state)) == "EXPIRED"


def test_rejection_and_generic_hold_release_guard(candidate, db):
    client, _, _, _, _ = candidate
    booking = create(candidate)
    with db.connect() as conn:
        hold_id = conn.scalar(select(holds.c.id))
    assert (
        client.post(f"/ops/inventory/holds/{hold_id}/release", json={}).status_code
        == 409
    )
    path = f"/ops/bookings/{booking['id']}/reject"
    assert client.post(path, json={}).json()["state"] == "FAILED"
    assert client.post(path, json={}).status_code == 200
    with db.connect() as conn:
        assert conn.scalar(select(holds.c.state)) == "RELEASED"


@pytest.mark.parametrize("target", ["bookings", "components"])
def test_database_rejects_confirmation_without_evidence(candidate, db, target):
    create(candidate)
    with pytest.raises(DBAPIError):
        with db.begin() as conn:
            table = bookings if target == "bookings" else booking_components
            conn.execute(update(table).values(state="CONFIRMED"))


@pytest.mark.parametrize("operation", ["create", "confirm", "expire"])
def test_audit_failure_rolls_back(candidate, db, monkeypatch, operation):
    client, _, _, _, body = candidate
    booking = None
    if operation != "create":
        booking = create(candidate)
    if operation == "expire":
        make_expired(db)

    def fail(*args):
        raise RuntimeError("private-audit-error")

    monkeypatch.setattr(audit, "record", fail)
    if operation == "create":
        response = client.post("/bookings", json=body)
    elif operation == "confirm":
        response = client.post(
            f"/ops/bookings/{booking['id']}/confirm",
            json={"vendor_confirmation_id": str(uuid4())},
        )
    else:
        with pytest.raises(RuntimeError):
            service.expire(db)
        response = None
    if response is not None:
        assert (
            response.status_code == 500 and "private-audit-error" not in response.text
        )
    with db.connect() as conn:
        if operation == "create":
            assert conn.scalar(select(func.count()).select_from(bookings)) == 0
            assert conn.scalar(select(func.count()).select_from(holds)) == 0
        else:
            assert (
                conn.scalar(select(bookings.c.state)) == "VENDOR_CONFIRMATION_PENDING"
            )
            assert conn.scalar(select(holds.c.state)) == "ACTIVE"


def test_confirmation_racing_expiry_has_consistent_result(candidate, db):
    _, actor, _, _, _ = candidate
    booking = create(candidate)
    make_expired(db)

    def confirm():
        try:
            service.change(
                db,
                UUID(booking["id"]),
                {"id": actor, "roles": ["ops_admin"]},
                "CONFIRMED",
                uuid4(),
            )
        except ValueError:
            pass

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(confirm), pool.submit(service.expire, db)]
        for future in futures:
            future.result()
    with db.connect() as conn:
        assert conn.scalar(select(bookings.c.state)) == "FAILED"
        assert conn.scalar(select(booking_components.c.vendor_confirmation_id)) is None


def test_booking_rate_limit(candidate):
    client, _, _, _, body = candidate
    for _ in range(15):
        assert client.post("/bookings", json=body).status_code == 201
    response = client.post("/bookings", json=body)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_retry_racing_confirmation_returns_consistent_states(candidate, db):
    _, actor, _, _, body = candidate
    booking = create(candidate)
    request = Create.model_validate(body)
    identity = {"id": actor, "roles": ["ops_admin"]}
    with ThreadPoolExecutor(max_workers=4) as pool:
        confirmation = pool.submit(
            service.change, db, UUID(booking["id"]), identity, "CONFIRMED", uuid4()
        )
        retries = [pool.submit(service.create, db, actor, request) for _ in range(3)]
        confirmation.result()
        for retry in retries:
            result = retry.result()
            assert result["state"] == result["component_state"]
    assert service.create(db, actor, request)["state"] == "CONFIRMED"
