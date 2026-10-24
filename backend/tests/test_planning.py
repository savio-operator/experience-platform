from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from app.modules.audit import service as audit
from app.modules.audit.models import audit_events
from app.modules.identity.models import user_roles
from app.modules.inventory.models import holds, inventory_slots
from app.modules.planning.models import slot_offers


def test_rank_limit_distinct_and_private_fields(setup, db):
    client, _, search, add = setup
    first, _ = add(300)
    add(50, service_id=first["service_id"], offset=1)
    for price in (200, 100, 400):
        add(price)
    response = client.post("/options", json=search)
    assert response.status_code == 200
    options = response.json()["options"]
    assert [o["customer_total_paise"] for o in options] == [50, 100, 200]
    assert len({o["service_id"] for o in options}) == 3
    assert all(
        o["availability"] == "AVAILABLE_VERIFIED" and not o["is_booking"]
        for o in options
    )
    assert all("cost" not in key and "margin" not in key for o in options for key in o)
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(holds)) == 0


@pytest.mark.parametrize(
    "state",
    [
        "UNKNOWN",
        "AVAILABLE_UNVERIFIED",
        "UNAVAILABLE",
        "EXPIRED",
        "BOOKING_PENDING",
        "CONFIRMED",
    ],
)
def test_unverified_states_excluded(setup, db, state):
    client, _, search, add = setup
    add()
    with db.begin() as conn:
        conn.execute(update(inventory_slots).values(state=state))
    assert client.post("/options", json=search).json() == {"options": []}


@pytest.mark.parametrize(
    "stale", ["availability", "offer", "missing_offer", "corrupt_offer"]
)
def test_stale_or_missing_evidence_excluded(setup, db, stale):
    client, _, search, add = setup
    slot, offer = add()
    with db.begin() as conn:
        if stale == "availability":
            conn.execute(
                update(inventory_slots).values(
                    verified_at=func.now() - timedelta(minutes=2),
                    verified_until=func.now() - timedelta(minutes=1),
                )
            )
        else:
            if stale == "offer":
                offer["verified_until"] = (
                    datetime.now(UTC) - timedelta(seconds=1)
                ).isoformat()
            if stale == "missing_offer":
                conn.execute(slot_offers.delete())
            else:
                conn.execute(
                    update(slot_offers).values(
                        payload=offer if stale == "offer" else {}
                    )
                )
    assert client.post("/options", json=search).json() == {"options": []}


def test_hard_constraint_and_soft_ranking(setup):
    client, _, search, add = setup
    deadline = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
    fact = dict(
        key="quiet", value=True, source_id=str(uuid4()), verified_until=deadline
    )
    add(50)
    preferred, _ = add(100, facts=[fact])
    search["requirements"] = [
        dict(key="quiet", strength="hard", operator="eq", expected=True)
    ]
    options = client.post("/options", json=search).json()["options"]
    assert [o["slot_id"] for o in options] == [preferred["id"]]
    search["requirements"][0]["strength"] = "soft"
    options = client.post("/options", json=search).json()["options"]
    assert [o["customer_total_paise"] for o in options] == [100, 50]


def test_expired_soft_fact_does_not_reject_option(setup, db):
    client, _, search, add = setup
    _, offer = add()
    offer["facts"] = [
        dict(
            key="quiet",
            value=True,
            source_id=str(uuid4()),
            verified_until=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        )
    ]
    with db.begin() as conn:
        conn.execute(update(slot_offers).values(payload=offer))
    search["requirements"] = [
        dict(key="quiet", strength="soft", operator="eq", expected=True)
    ]
    assert len(client.post("/options", json=search).json()["options"]) == 1
    search["requirements"][0]["strength"] = "hard"
    assert client.post("/options", json=search).json() == {"options": []}


def test_capacity_budget_margin_and_kind(setup):
    client, _, search, add = setup
    slot, offer = add(500, capacity=1)
    path = f"/ops/inventory/slots/{slot['id']}"
    search["budget_paise"] = 499
    assert client.post("/options", json=search).json() == {"options": []}
    search["budget_paise"] = 1000
    offer["minimum_margin_paise"] = 501
    assert client.put(path + "/offer", json=offer).status_code == 200
    assert client.post("/options", json=search).json() == {"options": []}
    offer["minimum_margin_paise"] = 0
    assert client.put(path + "/offer", json=offer).status_code == 200
    search["kind"] = "birthday_or_surprise"
    assert client.post("/options", json=search).json() == {"options": []}
    search["kind"] = "date"
    hold = client.post(
        path + "/holds",
        json={
            "quantity": 1,
            "expires_at": offer["verified_until"],
            "idempotency_key": str(uuid4()),
        },
    )
    assert hold.status_code == 201
    assert client.post("/options", json=search).json() == {"options": []}


def test_customer_can_search_but_not_supply_offer(setup, login):
    client, _, search, add = setup
    slot, offer = add()
    login("customer2@example.com")
    assert len(client.post("/options", json=search).json()["options"]) == 1
    assert (
        client.put(f"/ops/inventory/slots/{slot['id']}/offer", json=offer).status_code
        == 403
    )
    for field in (
        "unit_price_paise",
        "facts",
        "minimum_margin_paise",
        "verified_until",
    ):
        assert client.post("/options", json={**search, field: 0}).status_code == 422


def test_anonymous_forbidden(client):
    assert client.post("/options", json={}).status_code == 401
    assert (
        client.put(f"/ops/inventory/slots/{uuid4()}/offer", json={}).status_code == 401
    )


def test_offer_validation_audit_and_revocation(setup, db):
    client, actor, _, add = setup
    slot, offer = add()
    path = f"/ops/inventory/slots/{slot['id']}/offer"
    for patch in (
        {"unit_price_paise": True},
        {"unit_cost_paise": -1},
        {"facts": [{}]},
        {"location": "Elsewhere"},
    ):
        assert client.put(path, json={**offer, **patch}).status_code == 422
    missing = dict(offer)
    del missing["source_id"]
    assert client.put(path, json=missing).status_code == 422
    assert (
        client.put(
            path, json={**offer, "verified_until": datetime.now(UTC).isoformat()}
        ).status_code
        == 409
    )
    with db.connect() as conn:
        assert (
            conn.scalar(
                select(func.count())
                .select_from(audit_events)
                .where(
                    audit_events.c.resource_id == UUID(slot["id"]),
                    audit_events.c.changed_fields == ["offer"],
                )
            )
            == 1
        )
    with db.begin() as conn:
        conn.execute(user_roles.delete().where(user_roles.c.user_id == actor))
    assert client.put(path, json=offer).status_code == 403


def test_offer_audit_failure_rolls_back(setup, db, monkeypatch):
    client, _, _, add = setup
    slot, offer = add()

    def fail(*args):
        raise RuntimeError("private")

    monkeypatch.setattr(audit, "record", fail)
    assert (
        client.put(
            f"/ops/inventory/slots/{slot['id']}/offer",
            json={**offer, "unit_price_paise": 999},
        ).status_code
        == 500
    )
    with db.connect() as conn:
        assert conn.scalar(select(slot_offers.c.payload))["unit_price_paise"] == 100


def test_empty_and_rate_limit(setup):
    client, _, search, _ = setup
    for _ in range(15):
        assert client.post("/options", json=search).json() == {"options": []}
    response = client.post("/options", json=search)
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0


def test_invalid_search_window(setup):
    client, _, search, _ = setup
    for end in (
        search["starts_after"],
        (datetime.now(UTC) + timedelta(days=8)).isoformat(),
    ):
        assert (
            client.post("/options", json={**search, "ends_before": end}).status_code
            == 422
        )
