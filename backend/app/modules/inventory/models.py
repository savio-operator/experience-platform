from sqlalchemy import (
    UUID,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
)

from app.core.db import metadata

inventory_slots = Table(
    "inventory_slots",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("service_id", UUID, ForeignKey("services.id"), nullable=False, index=True),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("ends_at", DateTime(timezone=True), nullable=False),
    Column("release_at", DateTime(timezone=True), nullable=False),
    Column("capacity", Integer, nullable=False),
    Column("state", String(32), nullable=False, server_default="UNKNOWN"),
    Column("verified_at", DateTime(timezone=True)),
    Column("verified_until", DateTime(timezone=True)),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint("capacity > 0", name="slot_capacity_positive"),
    CheckConstraint(
        "ends_at > starts_at AND release_at <= starts_at", name="slot_time_order"
    ),
    CheckConstraint(
        "state IN ('UNKNOWN','AVAILABLE_UNVERIFIED','AVAILABLE_VERIFIED',"
        "'HELD','BOOKING_PENDING','CONFIRMED','UNAVAILABLE','EXPIRED')",
        name="slot_state",
    ),
    CheckConstraint(
        "verified_until IS NULL OR (verified_at IS NOT NULL AND "
        "verified_until > verified_at AND verified_until <= release_at)",
        name="slot_verification_window",
    ),
    UniqueConstraint(
        "service_id", "starts_at", "ends_at", name="slot_exact_window_unique"
    ),
)
holds = Table(
    "holds",
    metadata,
    Column("id", UUID, primary_key=True),
    Column(
        "slot_id", UUID, ForeignKey("inventory_slots.id"), nullable=False, index=True
    ),
    Column("created_by", UUID, ForeignKey("users.id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("idempotency_key", UUID, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("state", String(16), nullable=False, server_default="ACTIVE"),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint("quantity > 0", name="hold_quantity_positive"),
    CheckConstraint(
        "state IN ('ACTIVE','RELEASED','EXPIRED','CONFIRMED')", name="hold_state"
    ),
    UniqueConstraint("slot_id", "idempotency_key", name="hold_request_unique"),
)
