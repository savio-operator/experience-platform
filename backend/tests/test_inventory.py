from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from app.modules.audit import service as audit
from app.modules.audit.models import audit_events
from app.modules.inventory import service
from app.modules.inventory.models import holds, inventory_slots


@pytest.fixture
def inventory(ops):
    client, actor = ops
    vendor = client.post("/ops/vendors", json={"name": "Synthetic vendor"}).json()
    item = client.post(
        "/ops/services", json={"vendor_id": vendor["id"], "name": "Synthetic service"}
    ).json()
    now = datetime.now(UTC)
    body = dict(
        service_id=item["id"],
        starts_at=(now + timedelta(hours=2)).isoformat(),
        ends_at=(now + timedelta(hours=3)).isoformat(),
        release_at=(now + timedelta(hours=1)).isoformat(),
        capacity=1,
    )
    return client, actor, body


@pytest.fixture
def verified_slot(inventory):
    client, actor, body = inventory
    response = client.post("/ops/inventory/slots", json=body)
    assert response.status_code == 201
    slot = response.json()
    assert slot["state"] == "UNKNOWN" and slot["available_quantity"] == 0
    response = client.patch(
        f"/ops/inventory/slots/{slot['id']}/availability",
        json={"state": "AVAILABLE_VERIFIED", "verified_until": body["release_at"]},
    )
    assert response.status_code == 200
    return client, actor, response.json()


def hold_body(slot, quantity=1):
    return {
        "quantity": quantity,
        "expires_at": slot["verified_until"],
        "idempotency_key": str(uuid4()),
    }


def test_hold_release_and_idempotent_replay(verified_slot, db):
    client, _, slot = verified_slot
    path = f"/ops/inventory/slots/{slot['id']}"
    body = hold_body(slot)
    response = client.post(path + "/holds", json=body)
    assert response.status_code == 201
    hold = response.json()
    assert hold["state"] == "ACTIVE"
    assert client.get(path).json()["available_quantity"] == 0
    assert client.get(path).json()["state"] == "HELD"
    assert client.post(path + "/holds", json=body).json()["id"] == hold["id"]
    assert client.post(path + "/holds", json=hold_body(slot)).status_code == 409
    release = f"/ops/inventory/holds/{hold['id']}/release"
    assert client.post(release, json={}).json()["state"] == "RELEASED"
    assert client.post(release, json={}).json()["state"] == "RELEASED"
    assert client.post(path + "/holds", json=body).json()["state"] == "RELEASED"
    assert client.get(path).json()["available_quantity"] == 1
    with db.connect() as connection:
        actions = (
            connection.execute(
                select(audit_events.c.action).where(
                    audit_events.c.resource_id == UUID(hold["id"])
                )
            )
            .scalars()
            .all()
        )
        assert actions.count("created") == actions.count("released") == 1


def test_concurrent_capacity_cannot_be_exceeded(inventory, db):
    client, _, body = inventory
    body["capacity"] = 5
    slot = client.post("/ops/inventory/slots", json=body).json()
    path = f"/ops/inventory/slots/{slot['id']}"
    slot = client.patch(
        path + "/availability",
        json={"state": "AVAILABLE_VERIFIED", "verified_until": body["release_at"]},
    ).json()
    with ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(path + "/holds", json=hold_body(slot)), range(20)
            )
        )
    assert sum(r.status_code == 201 for r in responses) == 5
    assert sum(r.status_code == 409 for r in responses) == 15
    with db.connect() as connection:
        assert (
            connection.scalar(
                select(func.sum(holds.c.quantity)).where(holds.c.state == "ACTIVE")
            )
            == 5
        )
    assert client.get(path).json()["available_quantity"] == 0


def test_concurrent_retries_create_one_hold(verified_slot, db):
    client, _, slot = verified_slot
    body = hold_body(slot)
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    f"/ops/inventory/slots/{slot['id']}/holds", json=body
                ),
                range(6),
            )
        )
    assert all(r.status_code == 201 for r in responses)
    assert len({r.json()["id"] for r in responses}) == 1
    with db.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(holds)) == 1


def test_idempotency_payload_conflict(verified_slot):
    client, _, slot = verified_slot
    body = hold_body(slot)
    path = f"/ops/inventory/slots/{slot['id']}/holds"
    assert client.post(path, json=body).status_code == 201
    body["quantity"] = 2
    assert client.post(path, json=body).status_code == 409


def test_expired_hold_capacity_is_reused_and_audited(verified_slot, db):
    client, _, slot = verified_slot
    path = f"/ops/inventory/slots/{slot['id']}"
    old_body = hold_body(slot)
    old = client.post(path + "/holds", json=old_body).json()
    with db.begin() as connection:
        connection.execute(
            update(holds).values(expires_at=func.now() - timedelta(seconds=1))
        )
    assert client.get(path).json()["available_quantity"] == 1
    assert client.post(path + "/holds", json=hold_body(slot)).status_code == 201
    with db.connect() as connection:
        assert (
            connection.scalar(
                select(holds.c.state).where(holds.c.id == UUID(old["id"]))
            )
            == "EXPIRED"
        )
        assert (
            connection.scalar(
                select(func.count()).select_from(holds).where(holds.c.state == "ACTIVE")
            )
            == 1
        )
        assert (
            connection.scalar(
                select(audit_events.c.action).where(
                    audit_events.c.resource_id == UUID(old["id"]),
                    audit_events.c.action == "expired",
                )
            )
            == "expired"
        )


def test_stale_verification_cannot_be_restored_by_release(verified_slot, db):
    client, _, slot = verified_slot
    path = f"/ops/inventory/slots/{slot['id']}"
    hold = client.post(path + "/holds", json=hold_body(slot)).json()
    with db.begin() as connection:
        connection.execute(
            update(holds).values(expires_at=func.now() - timedelta(seconds=1))
        )
        connection.execute(
            update(inventory_slots).values(
                verified_at=func.now() - timedelta(minutes=2),
                verified_until=func.now() - timedelta(seconds=1),
            )
        )
    projected = client.get(path).json()
    assert (
        projected["state"] == "AVAILABLE_UNVERIFIED"
        and projected["available_quantity"] == 0
    )
    assert client.post(path + "/holds", json=hold_body(slot)).status_code == 409
    assert (
        client.post(f"/ops/inventory/holds/{hold['id']}/release", json={}).json()[
            "state"
        ]
        == "EXPIRED"
    )
    assert client.get(path).json()["state"] == "AVAILABLE_UNVERIFIED"


def test_release_deadline_is_terminal(verified_slot, db):
    client, _, slot = verified_slot
    path = f"/ops/inventory/slots/{slot['id']}"
    with db.begin() as connection:
        connection.execute(
            update(inventory_slots).values(
                verified_at=func.now() - timedelta(minutes=2),
                verified_until=func.now() - timedelta(seconds=2),
                release_at=func.now() - timedelta(seconds=1),
            )
        )
    assert client.post(path + "/refresh", json={}).json()["state"] == "EXPIRED"
    assert (
        client.patch(
            path + "/availability",
            json={
                "state": "AVAILABLE_VERIFIED",
                "verified_until": slot["verified_until"],
            },
        ).status_code
        == 409
    )
    assert client.post(path + "/holds", json=hold_body(slot)).status_code == 409


def test_unverified_unavailable_and_invalid_transitions(inventory):
    client, _, body = inventory
    slot = client.post("/ops/inventory/slots", json=body).json()
    path = f"/ops/inventory/slots/{slot['id']}"
    request = {
        "quantity": 1,
        "expires_at": body["release_at"],
        "idempotency_key": str(uuid4()),
    }
    assert client.post(path + "/holds", json=request).status_code == 409
    for state in ("UNAVAILABLE", "AVAILABLE_UNVERIFIED", "UNKNOWN"):
        assert (
            client.patch(path + "/availability", json={"state": state}).status_code
            == 200
        )
        assert client.post(path + "/holds", json=request).status_code == 409
    for state in ("CONFIRMED", "BOOKING_PENDING", "HELD", "EXPIRED"):
        assert (
            client.patch(path + "/availability", json={"state": state}).status_code
            == 422
        )
    assert (
        client.patch(
            path + "/availability", json={"state": "AVAILABLE_VERIFIED"}
        ).status_code
        == 422
    )


def test_active_holds_cannot_be_invalidated(verified_slot):
    client, _, slot = verified_slot
    path = f"/ops/inventory/slots/{slot['id']}"
    assert client.post(path + "/holds", json=hold_body(slot)).status_code == 201
    assert (
        client.patch(path + "/availability", json={"state": "UNAVAILABLE"}).status_code
        == 409
    )
    shortened = (
        datetime.fromisoformat(slot["verified_until"]) - timedelta(minutes=1)
    ).isoformat()
    assert (
        client.patch(
            path + "/availability",
            json={"state": "AVAILABLE_VERIFIED", "verified_until": shortened},
        ).status_code
        == 409
    )


@pytest.mark.parametrize("quantity", [0, -1, True, 2_147_483_648])
def test_quantity_validation(verified_slot, quantity):
    client, _, slot = verified_slot
    assert (
        client.post(
            f"/ops/inventory/slots/{slot['id']}/holds", json=hold_body(slot, quantity)
        ).status_code
        == 422
    )


def test_time_validation_and_unknown_records(inventory):
    client, _, body = inventory
    assert (
        client.post(
            "/ops/inventory/slots", json={**body, "starts_at": "2030-01-01T10:00:00"}
        ).status_code
        == 422
    )
    assert (
        client.post("/ops/inventory/slots", json={**body, "capacity": 0}).status_code
        == 422
    )
    assert (
        client.post(
            "/ops/inventory/slots", json={**body, "release_at": body["ends_at"]}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/ops/inventory/slots", json={**body, "service_id": str(uuid4())}
        ).status_code
        == 404
    )
    assert client.get(f"/ops/inventory/slots/{uuid4()}").status_code == 404
    assert (
        client.post(f"/ops/inventory/holds/{uuid4()}/release", json={}).status_code
        == 404
    )


def test_hold_time_must_be_within_freshness_window(verified_slot):
    client, _, slot = verified_slot
    for deadline in (
        datetime.now(UTC) - timedelta(seconds=1),
        datetime.fromisoformat(slot["verified_until"]) + timedelta(seconds=1),
    ):
        body = {**hold_body(slot), "expires_at": deadline.isoformat()}
        assert (
            client.post(
                f"/ops/inventory/slots/{slot['id']}/holds", json=body
            ).status_code
            == 409
        )


def test_concurrent_slot_creation_rejects_overlaps(inventory):
    client, _, body = inventory
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(
            pool.map(lambda _: client.post("/ops/inventory/slots", json=body), range(6))
        )
    assert sum(r.status_code == 201 for r in responses) == 1
    assert sum(r.status_code == 409 for r in responses) == 5
    adjacent = {
        **body,
        "starts_at": body["ends_at"],
        "ends_at": (
            datetime.fromisoformat(body["ends_at"]) + timedelta(hours=1)
        ).isoformat(),
    }
    assert client.post("/ops/inventory/slots", json=adjacent).status_code == 201


def test_audit_failure_rolls_back_hold(verified_slot, db, monkeypatch):
    client, _, slot = verified_slot

    def fail(*args):
        raise RuntimeError("private-error")

    monkeypatch.setattr(audit, "record", fail)
    response = client.post(
        f"/ops/inventory/slots/{slot['id']}/holds", json=hold_body(slot)
    )
    assert response.status_code == 500 and "private-error" not in response.text
    with db.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(holds)) == 0
        assert (
            connection.scalar(select(inventory_slots.c.state)) == "AVAILABLE_VERIFIED"
        )


def test_release_racing_new_hold_preserves_capacity(verified_slot, db):
    client, actor, slot = verified_slot
    old = client.post(
        f"/ops/inventory/slots/{slot['id']}/holds", json=hold_body(slot)
    ).json()
    values = {
        "quantity": 1,
        "expires_at": datetime.fromisoformat(slot["verified_until"]),
        "idempotency_key": uuid4(),
    }

    def create():
        try:
            return service.create_hold(db, actor, UUID(slot["id"]), values)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        release = pool.submit(service.release_hold, db, actor, UUID(old["id"]))
        new = pool.submit(create)
        release.result()
        result = new.result()
    if result is None:
        result = create()
    assert result is not None
    with db.connect() as connection:
        assert (
            connection.scalar(
                select(func.sum(holds.c.quantity)).where(holds.c.state == "ACTIVE")
            )
            == 1
        )


@pytest.mark.parametrize("authenticated", [False, True])
@pytest.mark.parametrize(
    "method,path,body",
    [
        (
            "post",
            "/slots",
            {
                "service_id": str(uuid4()),
                "starts_at": "2030-01-01T10:00:00Z",
                "ends_at": "2030-01-01T11:00:00Z",
                "release_at": "2030-01-01T09:00:00Z",
                "capacity": 1,
            },
        ),
        ("get", f"/slots/{uuid4()}", None),
        ("patch", f"/slots/{uuid4()}/availability", {"state": "UNAVAILABLE"}),
        ("post", f"/slots/{uuid4()}/refresh", {}),
        (
            "post",
            f"/slots/{uuid4()}/holds",
            {
                "quantity": 1,
                "expires_at": "2030-01-01T09:00:00Z",
                "idempotency_key": str(uuid4()),
            },
        ),
        ("post", f"/holds/{uuid4()}/release", {}),
    ],
)
def test_inventory_is_ops_only(client, login, authenticated, method, path, body):
    if authenticated:
        login()
    kwargs = {"headers": {"X-Role": "ops_admin"}}
    if body is not None:
        kwargs["json"] = body
    assert getattr(client, method)("/ops/inventory" + path, **kwargs).status_code == (
        403 if authenticated else 401
    )
