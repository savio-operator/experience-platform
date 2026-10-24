import asyncio
import hashlib
import hmac
import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.modules.audit import service as audit
from app.modules.bookings.models import bookings
from app.modules.payments import service
from app.modules.payments.gateway import (
    Event,
    InvalidSignature,
    Observation,
    get_gateway,
)
from app.modules.payments.models import payment_events, payments


class FixtureGateway:
    """Synthetic test wire/signature protocol; never a provider implementation."""

    def __init__(self):
        self.key = secrets.token_bytes(32)
        self.ledger = {}
        self.delay = 0
        self.after_charge_timeout = False
        self.initial_state = "PENDING"
        self.lookups = []

    def require_enabled(self):
        pass

    async def create(self, *, payment_id, amount_paise, currency):
        await asyncio.sleep(0)
        result = self.ledger.setdefault(
            payment_id,
            Observation(
                payment_id=payment_id,
                amount_paise=amount_paise,
                currency=currency,
                state=self.initial_state,
            ),
        )
        if self.after_charge_timeout:
            raise TimeoutError("private-gateway-error")
        return result

    async def lookup(self, *, payment_id):
        self.lookups.append(payment_id)
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.ledger.get(payment_id)

    def signed(self, event, timestamp=None):
        body = json.dumps(event).encode()
        timestamp = str(int(time.time()) if timestamp is None else timestamp)
        signature = hmac.new(
            self.key, timestamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        return body, {
            "Content-Type": "application/json",
            "X-Fixture-Time": timestamp,
            "X-Fixture-Signature": signature,
        }

    async def verify_webhook(self, body, headers):
        timestamp = headers.get("x-fixture-time", "")
        signature = headers.get("x-fixture-signature", "")
        expected = hmac.new(
            self.key, timestamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        if (
            not timestamp.isdigit()
            or abs(int(time.time()) - int(timestamp)) > 300
            or not hmac.compare_digest(expected, signature)
        ):
            raise InvalidSignature
        return Event.model_validate_json(body)


@pytest.fixture
def gateway(application):
    gateway = FixtureGateway()
    application.dependency_overrides[get_gateway] = lambda: gateway
    return gateway


@pytest.fixture
def payment_request(candidate):
    client, _, _, _, body = candidate
    response = client.post("/bookings", json=body)
    assert response.status_code == 201
    return {"booking_id": response.json()["id"], "idempotency_key": str(uuid4())}


def start(client, body):
    response = client.post("/payments", json=body)
    assert response.status_code == 202, response.text
    return response.json()


def event(payment, state="SUCCEEDED", key=None):
    return dict(
        payment_id=payment["id"],
        amount_paise=payment["amount_paise"],
        currency="INR",
        state=state,
        event_key=key or str(uuid4()),
    )


def send(client, gateway, payload):
    body, headers = gateway.signed(payload)
    return client.post("/payments/webhook", content=body, headers=headers)


def test_disabled_runtime_creates_no_record(client, payment_request, db):
    response = client.post("/payments", json=payment_request)
    assert response.status_code == 503
    assert client.post("/payments/webhook", json={}).status_code == 503
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(payments)) == 0


def test_concurrent_idempotency(client, payment_request, gateway, db):
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: start(client, payment_request), range(5)))
    assert len({p["id"] for p in results}) == 1
    assert len(gateway.ledger) == 1
    assert (
        client.post(
            "/payments", json={**payment_request, "idempotency_key": str(uuid4())}
        ).status_code
        == 409
    )
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(payments)) == 1


@pytest.mark.parametrize(
    "states",
    [
        ("PENDING", "FAILED", "SUCCEEDED", "FAILED"),
        ("SUCCEEDED", "PENDING", "FAILED"),
        ("FAILED", "PENDING", "SUCCEEDED"),
    ],
)
def test_out_of_order_and_duplicate_webhooks(
    client, payment_request, gateway, db, states
):
    payment = start(client, payment_request)
    for state in states:
        payload = event(payment, state)
        assert send(client, gateway, payload).status_code == 200
        assert send(client, gateway, payload).status_code == 200
    assert client.get(f"/payments/{payment['id']}").json()["state"] == "SUCCEEDED"
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(payment_events)) == len(
            states
        )
        assert conn.scalar(select(bookings.c.state)) == "VENDOR_CONFIRMATION_PENDING"


def test_invalid_signature_stale_and_tampered_payload(
    client, payment_request, gateway, db
):
    payment = start(client, payment_request)
    body, headers = gateway.signed(event(payment))
    assert (
        client.post(
            "/payments/webhook",
            content=body,
            headers={**headers, "X-Fixture-Signature": "invalid"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/payments/webhook", content=body + b" ", headers=headers
        ).status_code
        == 401
    )
    old_body, old_headers = gateway.signed(event(payment), timestamp=0)
    assert (
        client.post(
            "/payments/webhook", content=old_body, headers=old_headers
        ).status_code
        == 401
    )
    with db.connect() as conn:
        assert conn.scalar(select(payments.c.state)) == "PENDING"
        assert conn.scalar(select(func.count()).select_from(payment_events)) == 0


def test_webhook_amount_and_event_conflicts(client, payment_request, gateway):
    payment = start(client, payment_request)
    payload = event(payment)
    assert send(client, gateway, {**payload, "amount_paise": 101}).status_code == 409
    assert send(client, gateway, {**payload, "currency": "USD"}).status_code == 400
    assert send(client, gateway, payload).status_code == 200
    assert send(client, gateway, {**payload, "state": "FAILED"}).status_code == 409
    assert (
        send(
            client,
            gateway,
            {**payload, "event_key": str(uuid4()), "payment_id": str(uuid4())},
        ).status_code
        == 409
    )


def test_timeout_after_charge_reconciles_without_duplicate(
    client, payment_request, gateway, caplog
):
    gateway.after_charge_timeout = True
    gateway.initial_state = "SUCCEEDED"
    payment = start(client, payment_request)
    assert (
        payment["state"] == "PENDING" and payment["review_reason"] == "GATEWAY_UNKNOWN"
    )
    response = client.post(f"/ops/payments/{payment['id']}/reconcile", json={})
    assert response.status_code == 200 and response.json()["state"] == "SUCCEEDED"
    assert start(client, payment_request)["state"] == "SUCCEEDED"
    assert len(gateway.ledger) == 1
    assert "private-gateway-error" not in caplog.text


def test_lookup_timeout_keeps_unknown_recoverable(
    client, payment_request, gateway, monkeypatch
):
    payment = start(client, payment_request)
    monkeypatch.setattr(service, "TIMEOUT_SECONDS", 0.01)
    gateway.delay = 1
    result = client.post(f"/ops/payments/{payment['id']}/reconcile", json={}).json()
    assert result["state"] == "PENDING" and result["review_reason"] == "GATEWAY_UNKNOWN"
    gateway.delay = 0
    gateway.ledger[UUID(payment["id"])] = Observation.model_validate(
        {**gateway.ledger[UUID(payment["id"])].model_dump(), "state": "SUCCEEDED"}
    )
    assert (
        client.post(f"/ops/payments/{payment['id']}/reconcile", json={}).json()["state"]
        == "SUCCEEDED"
    )


@pytest.mark.parametrize("failure_first", [False, True])
def test_paid_booking_failure_is_flagged_not_refunded(
    client, payment_request, gateway, db, failure_first
):
    payment = start(client, payment_request)
    if failure_first:
        assert (
            client.post(
                f"/ops/bookings/{payment_request['booking_id']}/reject", json={}
            ).status_code
            == 200
        )
    assert send(client, gateway, event(payment)).status_code == 200
    if not failure_first:
        assert (
            client.post(
                f"/ops/bookings/{payment_request['booking_id']}/reject", json={}
            ).status_code
            == 200
        )
    result = client.get(f"/payments/{payment['id']}").json()
    assert (
        result["state"] == "SUCCEEDED" and result["review_reason"] == "BOOKING_FAILED"
    )
    # Gateway lookup is stale PENDING; recorded success must still win.
    result = client.post(f"/ops/payments/{payment['id']}/reconcile", json={}).json()
    assert result["state"] == "SUCCEEDED" and result["reconciliation_required"]
    with db.connect() as conn:
        assert conn.scalar(select(payments.c.review_reason)) == "BOOKING_FAILED"
        assert conn.scalar(select(bookings.c.state)) == "FAILED"


def test_audit_failure_rolls_back_webhook_and_retry_recovers(
    client, payment_request, gateway, db, monkeypatch
):
    payment = start(client, payment_request)
    payload = event(payment)
    original = audit.record

    def fail(*args):
        raise RuntimeError("private-audit")

    monkeypatch.setattr(audit, "record", fail)
    assert send(client, gateway, payload).status_code == 500
    with db.connect() as conn:
        assert conn.scalar(select(payments.c.state)) == "PENDING"
        assert conn.scalar(select(func.count()).select_from(payment_events)) == 0
    monkeypatch.setattr(audit, "record", original)
    assert send(client, gateway, payload).status_code == 200


def test_permissions_and_untrusted_amount(client, payment_request, gateway, login):
    payment = start(client, payment_request)
    assert (
        client.post(
            "/payments", json={**payment_request, "amount_paise": 1}
        ).status_code
        == 422
    )
    login("different@example.com")
    assert client.get(f"/payments/{payment['id']}").status_code == 404
    assert client.post("/payments", json=payment_request).status_code == 404
    assert (
        client.post(f"/ops/payments/{payment['id']}/reconcile", json={}).status_code
        == 403
    )
    client.cookies.clear()
    assert client.get(f"/payments/{payment['id']}").status_code == 401
    assert client.post("/payments", json=payment_request).status_code == 401


def test_batch_reconciliation_is_repeatable(client, payment_request, gateway, db):
    payment = start(client, payment_request)
    gateway.ledger[UUID(payment["id"])] = Observation.model_validate(
        {**gateway.ledger[UUID(payment["id"])].model_dump(), "state": "SUCCEEDED"}
    )
    assert asyncio.run(service.reconcile_batch(db, gateway)) == 1
    assert asyncio.run(service.reconcile_batch(db, gateway)) == 1
    assert client.get(f"/payments/{payment['id']}").json()["state"] == "SUCCEEDED"


def test_failed_booking_cannot_start_payment(client, payment_request, gateway, db):
    assert (
        client.post(
            f"/ops/bookings/{payment_request['booking_id']}/reject", json={}
        ).status_code
        == 200
    )
    assert client.post("/payments", json=payment_request).status_code == 409
    assert gateway.ledger == {}
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(payments)) == 0


def test_webhook_body_bound(client, gateway):
    assert (
        client.post(
            "/payments/webhook",
            content=b" " * 65537,
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )


def test_concurrent_duplicate_webhooks(client, payment_request, gateway, db):
    payment = start(client, payment_request)
    payload = event(payment)
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(lambda _: send(client, gateway, payload), range(5)))
    assert all(r.status_code == 200 for r in responses)
    with db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(payment_events)) == 1
        assert conn.scalar(select(payments.c.state)) == "SUCCEEDED"


def test_batch_rotates_unchanged_records(client, payment_request, gateway, candidate):
    first = start(client, payment_request)
    assert (
        client.post(
            f"/ops/bookings/{payment_request['booking_id']}/reject", json={}
        ).status_code
        == 200
    )
    body = {**candidate[4], "idempotency_key": str(uuid4())}
    second_booking = client.post("/bookings", json=body).json()
    second = start(
        client, {"booking_id": second_booking["id"], "idempotency_key": str(uuid4())}
    )
    engine = client.app.state.engine
    asyncio.run(service.reconcile_batch(engine, gateway, limit=1))
    asyncio.run(service.reconcile_batch(engine, gateway, limit=1))
    assert set(gateway.lookups[-2:]) == {UUID(first["id"]), UUID(second["id"])}
