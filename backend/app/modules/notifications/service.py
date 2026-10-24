import asyncio
from datetime import UTC, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.modules.audit import service as audit
from app.modules.bookings.models import booking_components, bookings
from app.modules.inventory.models import inventory_slots
from app.modules.inventory.service import lock_slot
from app.modules.notifications.models import notifications as records
from app.modules.payments.models import payments

SYSTEM_ACTOR = UUID(int=0)
MAX_ATTEMPTS = 3
RETRY_SECONDS = 60
LEASE_SECONDS = 30
TIMEOUT_SECONDS = 2


def eligible(conn, row, now):
    booking = (
        conn.execute(select(bookings).where(bookings.c.id == row["booking_id"]))
        .mappings()
        .one()
    )
    if booking["customer_id"] != row["customer_id"]:
        return False
    if row["kind"].startswith("PAYMENT_"):
        payment = (
            conn.execute(
                select(payments).where(
                    payments.c.id == row["payment_id"],
                    payments.c.booking_id == booking["id"],
                    payments.c.customer_id == row["customer_id"],
                )
            )
            .mappings()
            .first()
        )
        return payment is not None and payment["state"] == row["kind"].removeprefix(
            "PAYMENT_"
        )
    if row["payment_id"] is not None:
        return False
    if row["kind"] == "BOOKING_FAILED":
        return booking["state"] == "FAILED"
    if (
        row["kind"] not in {"BOOKING_CONFIRMED", "REMINDER"}
        or booking["state"] != "CONFIRMED"
    ):
        return False
    components = (
        conn.execute(
            select(booking_components).where(
                booking_components.c.booking_id == booking["id"]
            )
        )
        .mappings()
        .all()
    )
    if not components or any(
        c["state"] != "CONFIRMED"
        or c["vendor_confirmation_id"] is None
        or c["confirmed_by"] is None
        or c["confirmed_at"] is None
        for c in components
    ):
        return False
    if row["kind"] == "REMINDER":
        starts = conn.scalar(
            select(inventory_slots.c.starts_at).where(
                inventory_slots.c.id == booking["slot_id"]
            )
        )
        return now < starts and row["due_at"] < starts
    return True


def enqueue(conn, booking_id, kind, actor, payment_id=None, due_at=None):
    booking = (
        conn.execute(select(bookings).where(bookings.c.id == booking_id))
        .mappings()
        .one()
    )
    now = conn.scalar(select(func.clock_timestamp()))
    due = (due_at or now).astimezone(UTC)
    if kind == "REMINDER" and (due_at is None or due <= now):
        raise ValueError("Reminder must be scheduled in the future")
    row = dict(
        id=uuid4(),
        booking_id=booking_id,
        payment_id=payment_id,
        customer_id=booking["customer_id"],
        kind=kind,
        due_at=due,
    )
    if not eligible(conn, row, now):
        raise ValueError("Source state is not eligible")
    key = f"{kind}:{payment_id or booking_id}"
    if kind == "REMINDER":
        key += ":" + due.isoformat()
    identifier = conn.scalar(
        insert(records)
        .values(**row, dedupe_key=key)
        .on_conflict_do_nothing(index_elements=[records.c.dedupe_key])
        .returning(records.c.id)
    )
    if identifier:
        audit.record(
            conn,
            actor,
            "notification",
            identifier,
            "created",
            ["kind", "state", "due_at"],
        )
        return identifier
    return conn.scalar(select(records.c.id).where(records.c.dedupe_key == key))


def schedule(engine, booking_id, due_at, actor):
    with engine.begin() as conn:
        booking = (
            conn.execute(select(bookings).where(bookings.c.id == booking_id))
            .mappings()
            .first()
        )
        if booking is None:
            raise LookupError
        lock_slot(conn, booking["slot_id"])
        return {"id": enqueue(conn, booking_id, "REMINDER", actor, due_at=due_at)}


def view(row):
    return {
        k: row[k]
        for k in (
            "id",
            "booking_id",
            "payment_id",
            "kind",
            "state",
            "attempts",
            "due_at",
            "sent_at",
            "last_error",
        )
    }


def get(engine, identifier, identity):
    with engine.connect() as conn:
        query = select(records).where(records.c.id == identifier)
        if "ops_admin" not in identity["roles"]:
            query = query.where(records.c.customer_id == identity["id"])
        row = conn.execute(query).mappings().first()
        if row is None:
            raise LookupError
        return view(row)


def change(conn, identifier, **fields):
    conn.execute(update(records).where(records.c.id == identifier).values(**fields))
    audit.record(conn, SYSTEM_ACTOR, "notification", identifier, "updated", fields)


def claim(engine, identifier=None):
    with engine.begin() as conn:
        now = conn.scalar(select(func.clock_timestamp()))
        query = select(records).where(
            records.c.due_at <= now,
            or_(
                records.c.state == "PENDING",
                and_(records.c.state == "SENDING", records.c.lease_until <= now),
            ),
        )
        if identifier is not None:
            query = query.where(records.c.id == identifier)
        row = (
            conn.execute(
                query.order_by(records.c.due_at, records.c.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        if row["attempts"] >= MAX_ATTEMPTS:
            change(
                conn,
                row["id"],
                state="FAILED",
                last_error="RETRY_EXHAUSTED",
                lease_until=None,
                lease_id=None,
            )
            return {"id": row["id"], "exhausted": True}
        lease = uuid4()
        change(
            conn,
            row["id"],
            state="SENDING",
            attempts=row["attempts"] + 1,
            lease_id=lease,
            lease_until=now + timedelta(seconds=LEASE_SECONDS),
        )
        return {"id": row["id"], "lease_id": lease, "booking_id": row["booking_id"]}


async def send(adapter, row):
    return await asyncio.wait_for(
        adapter.send(
            notification_id=row["id"],
            recipient_id=row["customer_id"],
            booking_id=row["booking_id"],
            payment_id=row["payment_id"],
            kind=row["kind"],
        ),
        TIMEOUT_SECONDS,
    )


def dispatch(engine, adapter, identifier=None):
    adapter.require_enabled()  # Disabled delivery never claims or consumes retries.
    work = claim(engine, identifier)
    if work is None:
        return {"processed": False}
    if work.get("exhausted"):
        return {"processed": True, "state": "FAILED"}
    with engine.begin() as conn:
        booking = (
            conn.execute(select(bookings).where(bookings.c.id == work["booking_id"]))
            .mappings()
            .one()
        )
        # Bound adapter time while holding the same slot lock as source transitions.
        # A durable lease and stable adapter key recover crashes after acceptance.
        lock_slot(conn, booking["slot_id"])
        row = (
            conn.execute(
                select(records).where(records.c.id == work["id"]).with_for_update()
            )
            .mappings()
            .one()
        )
        if row["state"] != "SENDING" or row["lease_id"] != work["lease_id"]:
            return {"processed": False}
        now = conn.scalar(select(func.clock_timestamp()))
        if not eligible(conn, row, now):
            change(
                conn,
                row["id"],
                state="CANCELLED",
                last_error="STALE_STATE",
                lease_id=None,
                lease_until=None,
            )
            return {"processed": True, "state": "CANCELLED"}
        try:
            receipt = asyncio.run(send(adapter, row))
            if not isinstance(receipt, UUID):
                raise ValueError
        except Exception:
            state = "FAILED" if row["attempts"] >= MAX_ATTEMPTS else "PENDING"
            change(
                conn,
                row["id"],
                state=state,
                last_error="DELIVERY_UNCERTAIN",
                due_at=now + timedelta(seconds=RETRY_SECONDS),
                lease_id=None,
                lease_until=None,
            )
            return {"processed": True, "state": state}
        change(
            conn,
            row["id"],
            state="SENT",
            sent_at=conn.scalar(select(func.clock_timestamp())),
            receipt_id=receipt,
            last_error=None,
            lease_id=None,
            lease_until=None,
        )
        return {"processed": True, "state": "SENT"}


def dispatch_batch(engine, adapter, limit=100):
    adapter.require_enabled()
    count = 0
    for _ in range(limit):
        result = dispatch(engine, adapter)
        if not result["processed"]:
            break
        count += 1
    return count
