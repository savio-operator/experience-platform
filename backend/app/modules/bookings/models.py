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
from sqlalchemy.dialects.postgresql import JSONB

from app.core.db import metadata

bookings = Table(
    "bookings",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("customer_id", UUID, ForeignKey("users.id"), nullable=False, index=True),
    Column("slot_id", UUID, ForeignKey("inventory_slots.id"), nullable=False),
    Column("idempotency_key", UUID, nullable=False),
    Column("request", JSONB, nullable=False),
    Column("price_snapshot", JSONB, nullable=False),
    Column("total_paise", BigInteger, nullable=False),
    Column("state", String(32), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False, index=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("customer_id", "idempotency_key", name="booking_request_unique"),
    CheckConstraint(
        "state IN ('VENDOR_CONFIRMATION_PENDING','CONFIRMED','FAILED')",
        name="booking_state",
    ),
    CheckConstraint("total_paise >= 0", name="booking_total_nonnegative"),
)
booking_components = Table(
    "booking_components",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("booking_id", UUID, ForeignKey("bookings.id"), nullable=False, unique=True),
    Column("hold_id", UUID, ForeignKey("holds.id"), nullable=False, unique=True),
    Column("state", String(32), nullable=False),
    Column("vendor_confirmation_id", UUID),
    Column("confirmed_by", UUID, ForeignKey("users.id")),
    Column("confirmed_at", DateTime(timezone=True)),
    CheckConstraint(
        "state IN ('VENDOR_CONFIRMATION_PENDING','CONFIRMED','EXPIRED','REJECTED')",
        name="component_state",
    ),
    CheckConstraint(
        "state != 'CONFIRMED' OR (vendor_confirmation_id IS NOT NULL "
        "AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
        name="component_confirmation_required",
    ),
)
