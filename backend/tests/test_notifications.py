import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from app.modules.bookings.models import bookings
from app.modules.inventory.models import inventory_slots
from app.modules.notifications import service
from app.modules.notifications.delivery import get_delivery
from app.modules.notifications.models import notifications
from app.modules.payments import service as payment_service
from app.modules.payments.gateway import Observation


class FixtureDelivery:
    """No message content or real destination/provider. Stable-key acceptance."""

    def __init__(self):
        self.accepted = {}
        self.calls = []
        self.fail = False
        self.delay = 0
        self.after_accept_timeout = False

    def require_enabled(self):
        pass

    async def send(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("private-delivery-error")
        receipt = self.accepted.setdefault(kwargs["notification_id"], uuid4())
        if self.after_accept_timeout:
            raise TimeoutError("private-delivery-timeout")
        return receipt


@pytest.fixture
def adapter(application):
    adapter = FixtureDelivery()
    application.dependency_overrides[get_delivery] = lambda: adapter
    return adapter


@pytest.fixture
def booking(candidate):
    client, actor, slot, _, body = candidate
    response = client.post("/bookings", json=body)
    assert response.status_code == 201
    return client, actor, slot, response.json()


def confirm(booking, db):
    client, _, _, record = booking
    evidence = {"vendor_confirmation_id": str(uuid4())}
    assert (
        client.post(f"/ops/bookings/{record['id']}/confirm", json=evidence).status_code
        == 200
    )
    with db.connect() as conn:
        identifier = conn.scalar(
            select(notifications.c.id).where(
                notifications.c.kind == "BOOKING_CONFIRMED"
            )
        )
    return identifier, evidence


def test_generation_requires_verified_state(booking, db):
    client, actor, _, record = booking
    with db.begin() as conn:
        with pytest.raises(ValueError):
            service.enqueue(conn, UUID(record["id"]), "BOOKING_CONFIRMED", actor)
    assert (
        client.post(
            f"/ops/bookings/{record['id']}/reminders",
            json={"due_at": (datetime.now(UTC) + timedelta(minutes=30)).isoformat()},
        ).status_code
        == 409
    )
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(notifications)) == 0


def test_confirmation_duplicate_and_disabled_adapter(booking, db):
    client, _, _, record = booking
    identifier, evidence = confirm(booking, db)
    assert (
        client.post(f"/ops/bookings/{record['id']}/confirm", json=evidence).status_code
        == 200
    )
    assert (
        client.post(f"/ops/notifications/{identifier}/dispatch", json={}).status_code
        == 503
    )
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(notifications)) == 1
        assert conn.scalar(select(notifications.c.attempts)) == 0


def test_concurrent_dispatch_suppresses_duplicates(booking, db, adapter):
    identifier, _ = confirm(booking, db)
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda _: service.dispatch(db, adapter, identifier), range(5)))
    assert len(adapter.accepted) == len(adapter.calls) == 1
    row = service.get(db, identifier, {"id": booking[1], "roles": []})
    assert (
        row["state"] == "SENT" and row["attempts"] == 1 and row["sent_at"] is not None
    )
    assert adapter.calls[0]["recipient_id"] == booking[1]


def test_reminder_schedule_dedupe_and_stale_cancellation(booking, db, adapter):
    client, _, slot, record = booking
    confirm(booking, db)
    due = datetime.now(UTC) + timedelta(minutes=30)
    path = f"/ops/bookings/{record['id']}/reminders"
    first = client.post(path, json={"due_at": due.isoformat()})
    assert first.status_code == 201
    alternate = due.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert (
        client.post(path, json={"due_at": alternate.isoformat()}).json() == first.json()
    )
    identifier = UUID(first.json()["id"])
    assert not service.dispatch(db, adapter, identifier)["processed"]
    with db.begin() as conn:
        conn.execute(
            update(notifications)
            .where(notifications.c.id == identifier)
            .values(due_at=func.now() - timedelta(seconds=1))
        )
        conn.execute(
            update(inventory_slots)
            .where(inventory_slots.c.id == UUID(slot["id"]))
            .values(
                starts_at=func.now() - timedelta(seconds=1),
                release_at=func.now() - timedelta(seconds=2),
                verified_at=func.now() - timedelta(seconds=4),
                verified_until=func.now() - timedelta(seconds=3),
            )
        )
    assert service.dispatch(db, adapter, identifier)["state"] == "CANCELLED"
    assert adapter.calls == []


def retry_due(db, identifier):
    with db.begin() as conn:
        conn.execute(
            update(notifications)
            .where(notifications.c.id == identifier)
            .values(
                due_at=func.now() - timedelta(seconds=1),
                lease_until=func.now() - timedelta(seconds=1),
            )
        )


def test_bounded_failures_and_safe_logs(booking, db, adapter, caplog):
    identifier, _ = confirm(booking, db)
    adapter.fail = True
    for expected in ("PENDING", "PENDING", "FAILED"):
        assert service.dispatch(db, adapter, identifier)["state"] == expected
        retry_due(db, identifier)
    assert not service.dispatch(db, adapter, identifier)["processed"]
    assert len(adapter.calls) == 3 and "private-delivery-error" not in caplog.text


def test_timeout_after_acceptance_reuses_key(booking, db, adapter):
    identifier, _ = confirm(booking, db)
    adapter.after_accept_timeout = True
    assert service.dispatch(db, adapter, identifier)["state"] == "PENDING"
    adapter.after_accept_timeout = False
    retry_due(db, identifier)
    assert service.dispatch(db, adapter, identifier)["state"] == "SENT"
    assert len(adapter.accepted) == 1 and len(adapter.calls) == 2


def test_send_deadline(booking, db, adapter, monkeypatch):
    identifier, _ = confirm(booking, db)
    monkeypatch.setattr(service, "TIMEOUT_SECONDS", 0.01)
    adapter.delay = 1
    assert service.dispatch(db, adapter, identifier)["state"] == "PENDING"
    assert adapter.accepted == {}


def test_crash_after_acceptance_recovers_lease(booking, db, adapter, monkeypatch):
    identifier, _ = confirm(booking, db)
    original = service.audit.record

    def fail_on_receipt(conn, actor, resource, resource_id, action, fields):
        if "receipt_id" in fields:
            raise RuntimeError("commit failed")
        return original(conn, actor, resource, resource_id, action, fields)

    monkeypatch.setattr(service.audit, "record", fail_on_receipt)
    with pytest.raises(RuntimeError):
        service.dispatch(db, adapter, identifier)
    with db.connect() as conn:
        assert conn.scalar(select(notifications.c.state)) == "SENDING"
    monkeypatch.setattr(service.audit, "record", original)
    retry_due(db, identifier)
    assert service.dispatch(db, adapter, identifier)["state"] == "SENT"
    assert len(adapter.accepted) == 1


def test_transaction_rolls_back_if_queue_fails(booking, db, monkeypatch):
    client, _, _, record = booking

    def fail(*args, **kwargs):
        raise RuntimeError("private queue error")

    monkeypatch.setattr(service, "enqueue", fail)
    response = client.post(
        f"/ops/bookings/{record['id']}/confirm",
        json={"vendor_confirmation_id": str(uuid4())},
    )
    assert response.status_code == 500 and "private queue error" not in response.text
    with db.connect() as conn:
        assert conn.scalar(select(bookings.c.state)) == "VENDOR_CONFIRMATION_PENDING"
        assert conn.scalar(select(func.count()).select_from(notifications)) == 0


def test_payment_change_rechecks_source_before_send(booking, db, adapter):
    _, actor, _, record = booking
    payment, _ = payment_service.prepare(db, actor, UUID(record["id"]), uuid4())

    def observation(state):
        return Observation(
            payment_id=payment["id"],
            amount_paise=payment["amount_paise"],
            currency="INR",
            state=state,
        )

    payment_service.apply(db, observation("FAILED"))
    with db.connect() as conn:
        failed_id = conn.scalar(select(notifications.c.id))
    payment_service.apply(db, observation("SUCCEEDED"))
    payment_service.apply(db, observation("SUCCEEDED"))
    assert service.dispatch(db, adapter, failed_id)["state"] == "CANCELLED"
    assert service.dispatch_batch(db, adapter) == 1
    assert len(adapter.calls) == 1 and adapter.calls[0]["kind"] == "PAYMENT_SUCCEEDED"
    with db.connect() as conn:
        assert conn.scalar(select(bookings.c.state)) == "VENDOR_CONFIRMATION_PENDING"


def test_failed_booking_notification(booking, db, adapter):
    client, _, _, record = booking
    assert (
        client.post(f"/ops/bookings/{record['id']}/reject", json={}).status_code == 200
    )
    assert service.dispatch_batch(db, adapter) == 1
    assert adapter.calls[0]["kind"] == "BOOKING_FAILED"


def test_permissions_and_recipient_integrity(booking, db, adapter, login):
    client, actor, _, record = booking
    identifier, _ = confirm(booking, db)
    assert client.get(f"/notifications/{identifier}").status_code == 200
    login("other-notify@example.com")
    assert client.get(f"/notifications/{identifier}").status_code == 404
    assert (
        client.post(f"/ops/notifications/{identifier}/dispatch", json={}).status_code
        == 403
    )
    assert (
        client.post(
            f"/ops/bookings/{record['id']}/reminders",
            json={"due_at": datetime.now(UTC).isoformat()},
        ).status_code
        == 403
    )
    client.cookies.clear()
    assert client.get(f"/notifications/{identifier}").status_code == 401
    assert adapter.calls == []


def test_eligible_reminder_and_exhausted_crash_lease(booking, db, adapter):
    client, _, _, record = booking
    confirm(booking, db)
    response = client.post(
        f"/ops/bookings/{record['id']}/reminders",
        json={"due_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat()},
    )
    identifier = UUID(response.json()["id"])
    retry_due(db, identifier)
    assert service.dispatch(db, adapter, identifier)["state"] == "SENT"
    assert adapter.calls[0]["kind"] == "REMINDER"
    with db.begin() as conn:
        conn.execute(
            update(notifications)
            .where(notifications.c.kind == "BOOKING_CONFIRMED")
            .values(
                state="SENDING",
                attempts=3,
                lease_until=func.now() - timedelta(seconds=1),
            )
        )
    assert service.dispatch_batch(db, adapter) == 1
    assert len(adapter.calls) == 1
