import asyncio
import hashlib
from uuid import uuid4

from sqlalchemy import func, insert, select, update
from starlette.concurrency import run_in_threadpool

from app.modules.audit import service as audit
from app.modules.bookings.models import bookings
from app.modules.bookings.service import PENDING, SYSTEM_ACTOR
from app.modules.identity.models import users
from app.modules.inventory.service import lock_slot
from app.modules.payments.gateway import Event, Observation
from app.modules.payments.models import payment_events, payments

TIMEOUT_SECONDS = 5


def booking_failed(booking, now):
    return booking["state"] == "FAILED" or (
        booking["state"] == PENDING and booking["expires_at"] <= now
    )


def public(row, booking, now):
    review = row["review_reason"]
    if row["state"] == "SUCCEEDED":
        review = "BOOKING_FAILED" if booking_failed(booking, now) else None
    return {
        "id": row["id"],
        "booking_id": row["booking_id"],
        "state": row["state"],
        "amount_paise": row["amount_paise"],
        "currency": row["currency"],
        "review_reason": review,
        "reconciliation_required": review is not None,
    }


def prepare(engine, actor, booking_id, key):
    with engine.begin() as conn:
        conn.execute(
            select(users.c.id)
            .where(users.c.id == actor)
            .with_for_update(key_share=True)
        )
        booking = (
            conn.execute(
                select(bookings).where(
                    bookings.c.id == booking_id, bookings.c.customer_id == actor
                )
            )
            .mappings()
            .first()
        )
        if booking is None:
            raise LookupError
        slot = lock_slot(conn, booking["slot_id"])
        booking = (
            conn.execute(select(bookings).where(bookings.c.id == booking_id))
            .mappings()
            .one()
        )
        old = (
            conn.execute(
                select(payments).where(
                    payments.c.customer_id == actor, payments.c.idempotency_key == key
                )
            )
            .mappings()
            .first()
        )
        if old:
            if old["booking_id"] != booking_id:
                raise ValueError
            return dict(old), not booking_failed(
                booking, conn.scalar(select(func.clock_timestamp()))
            )
        if conn.scalar(
            select(payments.c.id).where(payments.c.booking_id == booking_id)
        ):
            raise ValueError
        now = conn.scalar(select(func.clock_timestamp()))
        if booking_failed(booking, now) or slot["starts_at"] <= now:
            raise ValueError
        row = (
            conn.execute(
                insert(payments)
                .values(
                    id=uuid4(),
                    booking_id=booking_id,
                    customer_id=actor,
                    idempotency_key=key,
                    amount_paise=booking["total_paise"],
                    currency="INR",
                    state="PENDING",
                    review_reason="GATEWAY_UNKNOWN",
                )
                .returning(payments)
            )
            .mappings()
            .one()
        )
        audit.record(
            conn, actor, "payment", row["id"], "created", ["state", "amount_paise"]
        )
        return dict(row), True


def locked(conn, identifier):
    row = (
        conn.execute(select(payments).where(payments.c.id == identifier))
        .mappings()
        .first()
    )
    if row is None:
        raise LookupError
    booking = (
        conn.execute(select(bookings).where(bookings.c.id == row["booking_id"]))
        .mappings()
        .one()
    )
    lock_slot(conn, booking["slot_id"])
    row = dict(
        conn.execute(
            select(payments).where(payments.c.id == identifier).with_for_update()
        )
        .mappings()
        .one()
    )
    booking = (
        conn.execute(select(bookings).where(bookings.c.id == row["booking_id"]))
        .mappings()
        .one()
    )
    return row, booking, conn.scalar(select(func.clock_timestamp()))


def get(engine, identifier, identity):
    with engine.begin() as conn:
        row, booking, now = locked(conn, identifier)
        if (
            "ops_admin" not in identity["roles"]
            and row["customer_id"] != identity["id"]
        ):
            raise LookupError
        return public(row, booking, now)


def store(conn, row, booking, now, state, unknown=False):
    review = "GATEWAY_UNKNOWN" if unknown else None
    if state == "SUCCEEDED":
        review = "BOOKING_FAILED" if booking_failed(booking, now) else None
    conn.execute(
        update(payments)
        .where(payments.c.id == row["id"])
        .values(state=state, review_reason=review, updated_at=now)
    )
    if state != row["state"] or review != row["review_reason"]:
        audit.record(
            conn,
            SYSTEM_ACTOR,
            "payment",
            row["id"],
            "updated",
            ["state", "review_reason"],
        )
        row.update(state=state, review_reason=review)
    return public(row, booking, now)


def unknown(engine, identifier):
    with engine.begin() as conn:
        row, booking, now = locked(conn, identifier)
        return store(conn, row, booking, now, row["state"], unknown=True)


def apply(engine, observation):
    with engine.begin() as conn:
        row, booking, now = locked(conn, observation.payment_id)
        if (
            observation.amount_paise != row["amount_paise"]
            or observation.currency != row["currency"]
        ):
            raise ValueError
        if isinstance(observation, Event):
            digest = hashlib.sha256(observation.model_dump_json().encode()).hexdigest()
            # Serialize event IDs even across payment records (replay/rebinding).
            conn.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtextextended(observation.event_key, 0)
                    )
                )
            )
            old = (
                conn.execute(
                    select(payment_events).where(
                        payment_events.c.event_key == observation.event_key
                    )
                )
                .mappings()
                .first()
            )
            if old:
                if old["payment_id"] != row["id"] or old["digest"] != digest:
                    raise ValueError
                return store(conn, row, booking, now, row["state"])
            conn.execute(
                insert(payment_events).values(
                    id=uuid4(),
                    event_key=observation.event_key,
                    payment_id=row["id"],
                    digest=digest,
                )
            )
        # A later failure/pending observation cannot erase recorded payment success.
        state = observation.state
        if row["state"] == "SUCCEEDED" or (
            row["state"] == "FAILED" and state == "PENDING"
        ):
            state = row["state"]
        return store(conn, row, booking, now, state)


def validated(result, identifier):
    result = Observation.model_validate(
        result.model_dump() if isinstance(result, Observation) else result
    )
    if result.payment_id != identifier:
        raise ValueError
    return result


async def initiate(engine, actor, booking_id, key, gateway):
    gateway.require_enabled()
    row, live = await run_in_threadpool(prepare, engine, actor, booking_id, key)
    if row["state"] != "PENDING" or not live:
        return await run_in_threadpool(
            get, engine, row["id"], {"id": actor, "roles": []}
        )
    try:
        result = await asyncio.wait_for(
            gateway.create(
                payment_id=row["id"],
                amount_paise=row["amount_paise"],
                currency=row["currency"],
            ),
            TIMEOUT_SECONDS,
        )
        result = validated(result, row["id"])
    except Exception:
        return await run_in_threadpool(unknown, engine, row["id"])
    try:
        return await run_in_threadpool(apply, engine, result)
    except ValueError:
        return await run_in_threadpool(unknown, engine, row["id"])


async def reconcile_one(engine, identifier, gateway):
    gateway.require_enabled()
    try:
        result = await asyncio.wait_for(
            gateway.lookup(payment_id=identifier), TIMEOUT_SECONDS
        )
        result = validated(result, identifier)
    except Exception:
        return await run_in_threadpool(unknown, engine, identifier)
    try:
        return await run_in_threadpool(apply, engine, result)
    except ValueError:
        return await run_in_threadpool(unknown, engine, identifier)


def reconciliation_ids(engine, limit):
    with engine.connect() as conn:
        return (
            conn.execute(
                select(payments.c.id)
                .order_by(payments.c.updated_at, payments.c.id)
                .limit(limit)
            )
            .scalars()
            .all()
        )


async def reconcile_batch(engine, gateway, limit=100):
    gateway.require_enabled()
    identifiers = await run_in_threadpool(reconciliation_ids, engine, limit)
    for identifier in identifiers:
        await reconcile_one(engine, identifier, gateway)
    return len(identifiers)
