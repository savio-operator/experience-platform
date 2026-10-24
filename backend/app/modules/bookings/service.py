from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update

from app.modules.audit import service as audit
from app.modules.bookings.models import booking_components as components
from app.modules.bookings.models import bookings
from app.modules.identity.models import users
from app.modules.inventory import service as inventory
from app.modules.inventory.models import holds
from app.modules.notifications import service as notifications
from app.modules.planning import service as planning

PENDING = "VENDOR_CONFIRMATION_PENDING"
SYSTEM_ACTOR = UUID(int=0)


def component(conn, booking_id):
    return dict(
        conn.execute(select(components).where(components.c.booking_id == booking_id))
        .mappings()
        .one()
    )


def public(row, item, now):
    expired = row["state"] == PENDING and row["expires_at"] <= now
    return {
        "id": row["id"],
        "slot_id": row["slot_id"],
        "state": "FAILED" if expired else row["state"],
        "component_state": "EXPIRED" if expired else item["state"],
        "total_paise": row["total_paise"],
        "expires_at": row["expires_at"],
    }


def transition(conn, actor, slot, row, item, target, now, evidence=None):
    if row["state"] != PENDING:
        raise ValueError("Booking cannot transition")
    confirmed = target == "CONFIRMED"
    if confirmed and evidence is None:
        raise ValueError("Vendor confirmation evidence required")
    component_state = (
        "CONFIRMED"
        if confirmed
        else ("EXPIRED" if row["expires_at"] <= now else "REJECTED")
    )
    fields = {"state": component_state}
    if confirmed:
        fields.update(
            vendor_confirmation_id=evidence, confirmed_by=actor, confirmed_at=now
        )
    conn.execute(
        update(components).where(components.c.id == item["id"]).values(**fields)
    )
    conn.execute(
        update(bookings).where(bookings.c.id == row["id"]).values(state=target)
    )
    hold_state = (
        "CONFIRMED"
        if confirmed
        else ("EXPIRED" if component_state == "EXPIRED" else "RELEASED")
    )
    conn.execute(
        update(holds).where(holds.c.id == item["hold_id"]).values(state=hold_state)
    )
    for resource, identifier in (
        ("booking", row["id"]),
        ("component", item["id"]),
        ("hold", item["hold_id"]),
    ):
        audit.record(
            conn,
            actor,
            resource,
            identifier,
            "confirmed" if confirmed else "failed",
            ["state"],
        )
    notifications.enqueue(
        conn, row["id"], "BOOKING_CONFIRMED" if confirmed else "BOOKING_FAILED", actor
    )
    row["state"] = target
    item.update(fields)
    quantity = inventory.active_quantity(conn, slot["id"], now)
    inventory.set_state(
        conn, actor, slot, inventory.effective_state(slot, now, quantity)
    )


def create(engine, actor, request):
    values = request.model_dump(mode="json")
    with engine.begin() as conn:
        # NO KEY UPDATE serializes customer requests but permits FK KEY SHARE
        # checks during concurrent ops confirmation (avoiding lock inversion).
        conn.execute(
            select(users.c.id)
            .where(users.c.id == actor)
            .with_for_update(key_share=True)
        )
        old = (
            conn.execute(
                select(bookings).where(
                    bookings.c.customer_id == actor,
                    bookings.c.idempotency_key == request.idempotency_key,
                )
            )
            .mappings()
            .first()
        )
        if old:
            if old["request"] != values:
                raise ValueError("Idempotency key conflicts with original request")
            inventory.lock_slot(conn, old["slot_id"])
            old = (
                conn.execute(select(bookings).where(bookings.c.id == old["id"]))
                .mappings()
                .one()
            )
            return public(
                old,
                component(conn, old["id"]),
                conn.scalar(select(func.clock_timestamp())),
            )
        slot = inventory.lock_slot(conn, request.slot_id)
        now = conn.scalar(select(func.clock_timestamp()))
        offer, result = planning.evaluate_offer(conn, slot, request, now)
        if (
            not result["accepted"]
            or result["customer_total_paise"] != request.expected_total_paise
        ):
            raise ValueError("Pricing or requirements changed; request a new option")
        deadline = min(
            [offer.verified_until]
            + [
                f.verified_until
                for f in offer.facts
                if f.key in {r.key for r in request.requirements}
                and f.verified_until > now
            ]
        )
        if request.expires_at > deadline:
            raise ValueError("Booking exceeds evidence window")
        hold = inventory.create_hold_in_transaction(
            conn,
            actor,
            request.slot_id,
            dict(
                quantity=request.quantity,
                expires_at=request.expires_at,
                idempotency_key=uuid4(),
            ),
        )
        row = dict(
            conn.execute(
                insert(bookings)
                .values(
                    id=uuid4(),
                    customer_id=actor,
                    slot_id=request.slot_id,
                    idempotency_key=request.idempotency_key,
                    request=values,
                    price_snapshot={
                        "offer": offer.model_dump(mode="json"),
                        "calculation": result,
                    },
                    total_paise=result["customer_total_paise"],
                    state=PENDING,
                    expires_at=request.expires_at,
                )
                .returning(bookings)
            )
            .mappings()
            .one()
        )
        item = dict(
            conn.execute(
                insert(components)
                .values(
                    id=uuid4(), booking_id=row["id"], hold_id=hold["id"], state=PENDING
                )
                .returning(components)
            )
            .mappings()
            .one()
        )
        audit.record(
            conn, actor, "booking", row["id"], "created", ["state", "price_snapshot"]
        )
        audit.record(
            conn, actor, "component", item["id"], "created", ["state", "hold_id"]
        )
        return public(row, item, now)


def accessible(conn, identifier, identity):
    query = select(bookings).where(bookings.c.id == identifier)
    if "ops_admin" not in identity["roles"]:
        query = query.where(bookings.c.customer_id == identity["id"])
    row = conn.execute(query).mappings().first()
    if row is None:
        raise LookupError("Booking not found")
    return dict(row)


def get(engine, identifier, identity):
    with engine.begin() as conn:
        row = accessible(conn, identifier, identity)
        inventory.lock_slot(conn, row["slot_id"])
        row = accessible(conn, identifier, identity)
        return public(
            row, component(conn, row["id"]), conn.scalar(select(func.clock_timestamp()))
        )


def change(engine, identifier, identity, target, evidence=None):
    if "ops_admin" not in identity["roles"]:
        raise PermissionError
    conflict = False
    with engine.begin() as conn:
        row = accessible(conn, identifier, identity)
        slot = inventory.lock_slot(conn, row["slot_id"])
        row = accessible(conn, identifier, identity)
        item = component(conn, identifier)
        now = conn.scalar(select(func.clock_timestamp()))
        if row["state"] == target:
            if target == "CONFIRMED" and item["vendor_confirmation_id"] != evidence:
                raise ValueError("Confirmation evidence conflicts with original")
        elif row["state"] == PENDING:
            held = (
                conn.execute(select(holds).where(holds.c.id == item["hold_id"]))
                .mappings()
                .one()
            )
            if (
                row["expires_at"] <= now
                or held["state"] != "ACTIVE"
                or held["expires_at"] <= now
            ):
                transition(conn, identity["id"], slot, row, item, "FAILED", now)
                conflict = target == "CONFIRMED"
            else:
                transition(conn, identity["id"], slot, row, item, target, now, evidence)
        else:
            raise ValueError("Booking cannot transition")
        result = public(row, item, now)
    if conflict:
        raise ValueError("Booking expired or reservation is unavailable")
    return result


def expire(engine, limit=100):
    count = 0
    with engine.connect() as conn:
        identifiers = (
            conn.execute(
                select(bookings.c.id)
                .where(
                    bookings.c.state == PENDING,
                    bookings.c.expires_at <= func.clock_timestamp(),
                )
                .order_by(bookings.c.expires_at)
                .limit(limit)
            )
            .scalars()
            .all()
        )
    for identifier in identifiers:
        with engine.begin() as conn:
            row = dict(
                conn.execute(select(bookings).where(bookings.c.id == identifier))
                .mappings()
                .one()
            )
            slot = inventory.lock_slot(conn, row["slot_id"])
            row = dict(
                conn.execute(select(bookings).where(bookings.c.id == identifier))
                .mappings()
                .one()
            )
            now = conn.scalar(select(func.clock_timestamp()))
            if row["state"] == PENDING and row["expires_at"] <= now:
                transition(
                    conn,
                    SYSTEM_ACTOR,
                    slot,
                    row,
                    component(conn, identifier),
                    "FAILED",
                    now,
                )
                count += 1
    return count
