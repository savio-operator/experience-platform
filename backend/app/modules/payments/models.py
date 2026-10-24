from sqlalchemy import (
    UUID,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
    func,
)

from app.core.db import metadata

payments = Table(
    "payments",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("booking_id", UUID, ForeignKey("bookings.id"), nullable=False, unique=True),
    Column("customer_id", UUID, ForeignKey("users.id"), nullable=False),
    Column("idempotency_key", UUID, nullable=False),
    Column("amount_paise", BigInteger, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("state", String(16), nullable=False),
    Column("review_reason", String(32)),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("customer_id", "idempotency_key", name="payment_request_unique"),
    CheckConstraint("amount_paise >= 0", name="payment_amount_nonnegative"),
    CheckConstraint("currency = 'INR'", name="payment_currency"),
    CheckConstraint("state IN ('PENDING','FAILED','SUCCEEDED')", name="payment_state"),
    CheckConstraint(
        "review_reason IS NULL OR review_reason IN "
        "('GATEWAY_UNKNOWN','BOOKING_FAILED')",
        name="payment_review_reason",
    ),
)
payment_events = Table(
    "payment_events",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("event_key", String(128), nullable=False, unique=True),
    Column("payment_id", UUID, ForeignKey("payments.id"), nullable=False),
    Column("digest", String(64), nullable=False),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)
