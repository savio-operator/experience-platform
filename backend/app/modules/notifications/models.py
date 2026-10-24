from sqlalchemy import (
    UUID,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    func,
)

from app.core.db import metadata

notifications = Table(
    "notifications",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("booking_id", UUID, ForeignKey("bookings.id"), nullable=False),
    Column("payment_id", UUID, ForeignKey("payments.id")),
    Column("customer_id", UUID, ForeignKey("users.id"), nullable=False, index=True),
    Column("kind", String(32), nullable=False),
    Column("dedupe_key", String(160), nullable=False, unique=True),
    Column("state", String(16), nullable=False, server_default="PENDING"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("due_at", DateTime(timezone=True), nullable=False, index=True),
    Column("lease_until", DateTime(timezone=True)),
    Column("lease_id", UUID),
    Column("receipt_id", UUID),
    Column("sent_at", DateTime(timezone=True)),
    Column("last_error", String(32)),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint(
        "kind IN ('BOOKING_CONFIRMED','BOOKING_FAILED','REMINDER',"
        "'PAYMENT_SUCCEEDED','PAYMENT_FAILED')",
        name="notification_kind",
    ),
    CheckConstraint(
        "state IN ('PENDING','SENDING','SENT','FAILED','CANCELLED')",
        name="notification_state",
    ),
    CheckConstraint("attempts >= 0 AND attempts <= 3", name="notification_attempts"),
    CheckConstraint(
        "state != 'SENT' OR (receipt_id IS NOT NULL AND sent_at IS NOT NULL)",
        name="notification_receipt",
    ),
)
