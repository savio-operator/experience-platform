from uuid import uuid4

from sqlalchemy import and_, case, func, insert, or_, select, update

from app.modules.audit import service as audit
from app.modules.bookings.models import bookings
from app.modules.bookings.service import PENDING
from app.modules.identity.models import roles, user_roles
from app.modules.inventory.service import lock_slot
from app.modules.notifications.models import notifications
from app.modules.ops.models import case_actions, cases
from app.modules.payments import service as payment_service
from app.modules.payments.models import payments


def failed(now):
    return or_(
        bookings.c.state == "FAILED",
        and_(bookings.c.state == PENDING, bookings.c.expires_at <= now),
    )


def queue(engine, kind, limit, after=None):
    with engine.connect() as conn:
        now = conn.scalar(select(func.clock_timestamp()))
        if kind in {"pending-confirmations", "failed-bookings"}:
            table = bookings
            query = select(
                bookings.c.id, bookings.c.state, bookings.c.expires_at
            ).where(
                failed(now)
                if kind == "failed-bookings"
                else and_(bookings.c.state == PENDING, bookings.c.expires_at > now)
            )
        elif kind == "payment-review":
            table = payments
            query = (
                select(
                    payments.c.id,
                    payments.c.booking_id,
                    payments.c.state,
                    payments.c.amount_paise,
                    payments.c.currency,
                    case(
                        (
                            and_(payments.c.state == "SUCCEEDED", failed(now)),
                            "BOOKING_FAILED",
                        ),
                        else_=payments.c.review_reason,
                    ).label("review_reason"),
                )
                .join(bookings)
                .where(
                    or_(
                        payments.c.state == "PENDING",
                        payments.c.review_reason.is_not(None),
                        and_(payments.c.state == "SUCCEEDED", failed(now)),
                    )
                )
            )
        elif kind == "failed-notifications":
            table = notifications
            query = select(
                notifications.c.id,
                notifications.c.booking_id,
                notifications.c.state,
                notifications.c.last_error,
            ).where(notifications.c.state == "FAILED")
        else:
            table = cases
            query = select(cases).where(cases.c.state == "ESCALATED")
        if after:
            query = query.where(table.c.id > after)
        rows = [
            dict(r)
            for r in conn.execute(query.order_by(table.c.id).limit(limit)).mappings()
        ]
        # Expiry is effective even before the expiry job persists the transition.
        if kind == "failed-bookings":
            for row in rows:
                row["state"] = "FAILED"
        return rows


def read(conn, identifier):
    row = conn.execute(select(cases).where(cases.c.id == identifier)).mappings().first()
    if row is None:
        raise LookupError
    return dict(row)


def public(conn, row):
    book = (
        conn.execute(select(bookings).where(bookings.c.id == row["booking_id"]))
        .mappings()
        .one()
    )
    payment = (
        conn.execute(select(payments).where(payments.c.booking_id == book["id"]))
        .mappings()
        .first()
    )
    now = conn.scalar(select(func.clock_timestamp()))
    view = dict(row)
    view["payment"] = payment_service.public(payment, book, now) if payment else None
    view["financial_follow_up_required"] = bool(
        payment
        and (
            payment["state"] == "PENDING" or view["payment"]["reconciliation_required"]
        )
    )
    view["failed_notification_ids"] = list(
        conn.scalars(
            select(notifications.c.id).where(
                notifications.c.booking_id == book["id"],
                notifications.c.state == "FAILED",
            )
        )
    )
    return view


def create(engine, actor, booking_id):
    with engine.begin() as conn:
        book = (
            conn.execute(select(bookings).where(bookings.c.id == booking_id))
            .mappings()
            .first()
        )
        if book is None:
            raise LookupError
        # Match booking/payment lock order. One durable case per booking is the
        # natural idempotency key, including concurrent creation and later issues.
        lock_slot(conn, book["slot_id"])
        old = (
            conn.execute(select(cases).where(cases.c.booking_id == booking_id))
            .mappings()
            .first()
        )
        if old:
            return public(conn, old)
        row = (
            conn.execute(
                insert(cases).values(id=uuid4(), booking_id=booking_id).returning(cases)
            )
            .mappings()
            .one()
        )
        audit.record(conn, actor, "case", row["id"], "created", ["booking_id", "state"])
        return public(conn, row)


def get(engine, identifier):
    with engine.begin() as conn:
        return public(conn, read(conn, identifier))


def history(engine, identifier, limit, after=None):
    with engine.connect() as conn:
        read(conn, identifier)
        query = select(case_actions).where(case_actions.c.case_id == identifier)
        if after:
            query = query.where(case_actions.c.id > after)
        return [
            dict(r)
            for r in conn.execute(
                query.order_by(case_actions.c.id).limit(limit)
            ).mappings()
        ]


def act(engine, actor, identifier, body):
    values = body.model_dump(mode="json")
    with engine.begin() as conn:
        row = read(conn, identifier)
        book = (
            conn.execute(select(bookings).where(bookings.c.id == row["booking_id"]))
            .mappings()
            .one()
        )
        lock_slot(conn, book["slot_id"])
        row = dict(
            conn.execute(
                select(cases).where(cases.c.id == identifier).with_for_update()
            )
            .mappings()
            .one()
        )
        old = (
            conn.execute(
                select(case_actions).where(
                    case_actions.c.case_id == identifier,
                    case_actions.c.idempotency_key == body.idempotency_key,
                )
            )
            .mappings()
            .first()
        )
        if old:
            if old["request"] != values or old["actor_id"] != actor:
                raise ValueError("Idempotency key conflicts with original action")
            return public(conn, row)
        if body.version != row["version"]:
            raise ValueError("Case version changed; reload before updating")
        if row["state"] == "RESOLVED" and body.action != "reopen":
            raise ValueError("Reopen the case before recording further work")
        fields = {"version": row["version"] + 1}
        if body.action == "assign":
            eligible = conn.scalar(
                select(user_roles.c.user_id)
                .join(roles)
                .where(
                    user_roles.c.user_id == body.assigned_to,
                    roles.c.name == "ops_admin",
                )
            )
            if not eligible:
                raise ValueError("Assignee must be an ops administrator")
            fields["assigned_to"] = body.assigned_to
        elif body.action == "escalate":
            fields["state"] = "ESCALATED"
        elif body.action == "reopen":
            if row["state"] != "RESOLVED":
                raise ValueError("Only resolved cases can reopen")
            fields.update(state="OPEN", resolution_evidence_id=None)
        elif body.action == "resolve":
            view = public(conn, row)
            book = (
                conn.execute(select(bookings).where(bookings.c.id == row["booking_id"]))
                .mappings()
                .one()
            )
            if not row["assigned_to"] or book["state"] == PENDING:
                raise ValueError("Assignment and a terminal booking state are required")
            if view["financial_follow_up_required"] or view["failed_notification_ids"]:
                raise ValueError(
                    "Unresolved payment or notification work requires follow-up"
                )
            fields.update(state="RESOLVED", resolution_evidence_id=body.evidence_id)
        conn.execute(update(cases).where(cases.c.id == identifier).values(**fields))
        conn.execute(
            insert(case_actions).values(
                id=uuid4(),
                case_id=identifier,
                actor_id=actor,
                idempotency_key=body.idempotency_key,
                request=values,
            )
        )
        audit.record(
            conn, actor, "case", identifier, "updated", [*fields, "action_evidence"]
        )
        row.update(fields)
        return public(conn, row)
