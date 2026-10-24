from uuid import uuid4

from sqlalchemy import and_, func, insert, or_, select, update

from app.modules.audit import service as audit
from app.modules.catalogue.models import services
from app.modules.inventory.models import holds
from app.modules.inventory.models import inventory_slots as slots

STATE_ACTION = {
    "UNKNOWN": "unknown",
    "AVAILABLE_UNVERIFIED": "unverified",
    "AVAILABLE_VERIFIED": "verified",
    "HELD": "held",
    "UNAVAILABLE": "unavailable",
    "EXPIRED": "expired",
}
RESERVED_STATES = {"BOOKING_PENDING", "CONFIRMED"}


def lock_slot(connection, slot_id):
    row = (
        connection.execute(select(slots).where(slots.c.id == slot_id).with_for_update())
        .mappings()
        .first()
    )
    if row is None:
        raise LookupError("Slot not found")
    return dict(row)


def active_quantity(connection, slot_id, now):
    return connection.scalar(
        select(func.coalesce(func.sum(holds.c.quantity), 0)).where(
            holds.c.slot_id == slot_id,
            or_(
                holds.c.state == "CONFIRMED",
                and_(holds.c.state == "ACTIVE", holds.c.expires_at > now),
            ),
        )
    )


def effective_state(slot, now, quantity):
    if slot["state"] in RESERVED_STATES:
        return slot["state"]
    if slot["release_at"] <= now:
        return "EXPIRED"
    if slot["state"] in {"AVAILABLE_VERIFIED", "HELD"}:
        if slot["verified_until"] is None or slot["verified_until"] <= now:
            return "AVAILABLE_UNVERIFIED"
        return "HELD" if quantity else "AVAILABLE_VERIFIED"
    return slot["state"]


def set_state(connection, actor_id, slot, state):
    if slot["state"] != state:
        connection.execute(
            update(slots).where(slots.c.id == slot["id"]).values(state=state)
        )
        slot["state"] = state
        audit.record(
            connection,
            actor_id,
            "inventory_slot",
            slot["id"],
            STATE_ACTION[state],
            ["state"],
        )


def reconcile(connection, actor_id, slot, now):
    expired = (
        connection.execute(
            update(holds)
            .where(
                holds.c.slot_id == slot["id"],
                holds.c.state == "ACTIVE",
                holds.c.expires_at <= now,
            )
            .values(state="EXPIRED")
            .returning(holds.c.id)
        )
        .scalars()
        .all()
    )
    for hold_id in expired:
        audit.record(connection, actor_id, "hold", hold_id, "expired", ["state"])
    quantity = active_quantity(connection, slot["id"], now)
    set_state(connection, actor_id, slot, effective_state(slot, now, quantity))
    return quantity


def snapshot(slot, now, quantity):
    state = effective_state(slot, now, quantity)
    remaining = (
        slot["capacity"] - quantity if state in {"AVAILABLE_VERIFIED", "HELD"} else 0
    )
    return {
        **slot,
        "state": state,
        "held_quantity": quantity,
        "available_quantity": max(0, remaining),
    }


def create_slot(engine, actor_id, values):
    with engine.begin() as connection:
        # Serialize slot creation per service so overlapping windows cannot race.
        service_id = connection.scalar(
            select(services.c.id)
            .where(services.c.id == values["service_id"])
            .with_for_update()
        )
        if service_id is None:
            raise LookupError("Service not found")
        now = connection.scalar(select(func.clock_timestamp()))
        if not (now < values["release_at"] <= values["starts_at"] < values["ends_at"]):
            raise ValueError("Invalid slot time window")
        overlap = connection.scalar(
            select(slots.c.id)
            .where(
                slots.c.service_id == service_id,
                slots.c.starts_at < values["ends_at"],
                slots.c.ends_at > values["starts_at"],
            )
            .limit(1)
        )
        if overlap is not None:
            raise ValueError("Service window overlaps an existing slot")
        row = (
            connection.execute(
                insert(slots).values(id=uuid4(), **values).returning(slots)
            )
            .mappings()
            .one()
        )
        audit.record(
            connection, actor_id, "inventory_slot", row["id"], "created", values
        )
        return snapshot(dict(row), now, 0)


def get_slot(engine, slot_id):
    with engine.begin() as connection:
        slot = lock_slot(connection, slot_id)
        now = connection.scalar(select(func.clock_timestamp()))
        # Reads project time-based expiry but never mutate or emit audit events.
        return snapshot(slot, now, active_quantity(connection, slot_id, now))


def refresh_slot(engine, actor_id, slot_id):
    with engine.begin() as connection:
        slot = lock_slot(connection, slot_id)
        now = connection.scalar(select(func.clock_timestamp()))
        quantity = reconcile(connection, actor_id, slot, now)
        return snapshot(slot, now, quantity)


def set_availability(engine, actor_id, slot_id, state, verified_until):
    with engine.begin() as connection:
        slot = lock_slot(connection, slot_id)
        now = connection.scalar(select(func.clock_timestamp()))
        quantity = reconcile(connection, actor_id, slot, now)
        if slot["state"] in RESERVED_STATES | {"EXPIRED"}:
            raise ValueError("Slot cannot change availability")
        if quantity and state != "AVAILABLE_VERIFIED":
            raise ValueError("Release active holds before changing availability")
        if state == "AVAILABLE_VERIFIED":
            if verified_until is None or not now < verified_until <= slot["release_at"]:
                raise ValueError("Invalid verification window")
            last_expiry = connection.scalar(
                select(func.max(holds.c.expires_at)).where(
                    holds.c.slot_id == slot_id,
                    holds.c.state.in_(["ACTIVE", "CONFIRMED"]),
                )
            )
            if last_expiry is not None and verified_until < last_expiry:
                raise ValueError("Verification cannot end before active holds")
            slot.update(verified_at=now, verified_until=verified_until)
        else:
            slot.update(verified_at=None, verified_until=None)
        target = "HELD" if quantity else state
        connection.execute(
            update(slots)
            .where(slots.c.id == slot_id)
            .values(
                state=target,
                verified_at=slot["verified_at"],
                verified_until=slot["verified_until"],
            )
        )
        slot["state"] = target
        audit.record(
            connection,
            actor_id,
            "inventory_slot",
            slot_id,
            STATE_ACTION[state],
            ["state", "verified_at", "verified_until"],
        )
        return snapshot(slot, now, quantity)


def create_hold(engine, actor_id, slot_id, values):
    with engine.begin() as connection:
        return create_hold_in_transaction(connection, actor_id, slot_id, values)


def create_hold_in_transaction(connection, actor_id, slot_id, values):
    slot = lock_slot(connection, slot_id)
    now = connection.scalar(select(func.clock_timestamp()))
    quantity = reconcile(connection, actor_id, slot, now)
    existing = (
        connection.execute(
            select(holds).where(
                holds.c.slot_id == slot_id,
                holds.c.idempotency_key == values["idempotency_key"],
            )
        )
        .mappings()
        .first()
    )
    if existing:
        if existing["created_by"] != actor_id or any(
            existing[k] != v for k, v in values.items()
        ):
            raise ValueError("Idempotency key conflicts with the original request")
        return dict(existing)
    if slot["state"] not in {"AVAILABLE_VERIFIED", "HELD"}:
        raise ValueError("Slot availability is not verified and current")
    if (
        not now
        < values["expires_at"]
        <= min(slot["release_at"], slot["verified_until"])
    ):
        raise ValueError("Hold exceeds the verified release window")
    if values["quantity"] > slot["capacity"] - quantity:
        raise ValueError("Insufficient available capacity")
    row = (
        connection.execute(
            insert(holds)
            .values(
                id=uuid4(),
                slot_id=slot_id,
                created_by=actor_id,
                **values,
            )
            .returning(holds)
        )
        .mappings()
        .one()
    )
    audit.record(connection, actor_id, "hold", row["id"], "created", values)
    set_state(connection, actor_id, slot, "HELD")
    return dict(row)


def release_hold(engine, actor_id, hold_id):
    with engine.begin() as connection:
        slot_id = connection.scalar(
            select(holds.c.slot_id).where(holds.c.id == hold_id)
        )
        if slot_id is None:
            raise LookupError("Hold not found")
        slot = lock_slot(connection, slot_id)
        now = connection.scalar(select(func.clock_timestamp()))
        from app.modules.bookings.models import booking_components

        if (
            connection.scalar(
                select(booking_components.c.id).where(
                    booking_components.c.hold_id == hold_id
                )
            )
            is not None
        ):
            raise ValueError("Booking holds must use booking transitions")
        reconcile(connection, actor_id, slot, now)
        row = (
            connection.execute(select(holds).where(holds.c.id == hold_id))
            .mappings()
            .one()
        )
        if row["state"] == "ACTIVE":
            row = (
                connection.execute(
                    update(holds)
                    .where(holds.c.id == hold_id)
                    .values(state="RELEASED")
                    .returning(holds)
                )
                .mappings()
                .one()
            )
            audit.record(connection, actor_id, "hold", hold_id, "released", ["state"])
            quantity = active_quantity(connection, slot_id, now)
            set_state(connection, actor_id, slot, effective_state(slot, now, quantity))
        return dict(row)
