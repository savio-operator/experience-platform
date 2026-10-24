from sqlalchemy import (
    ARRAY,
    UUID,
    CheckConstraint,
    Column,
    DateTime,
    String,
    Table,
    func,
)

from app.core.db import metadata

# Actor/resource UUIDs remain historical references, including after future deletion.
audit_events = Table(
    "audit_events",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("actor_id", UUID, nullable=False),
    Column("resource_type", String(16), nullable=False),
    Column("resource_id", UUID, nullable=False, index=True),
    Column("action", String(16), nullable=False),
    Column("changed_fields", ARRAY(String(64)), nullable=False),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint(
        "resource_type IN ('vendor', 'service', 'inventory_slot', 'hold')",
        name="audit_resource_type",
    ),
    CheckConstraint(
        "action IN ('created', 'updated', 'unknown', 'unverified', 'verified', "
        "'held', 'unavailable', 'expired', 'released')",
        name="audit_action",
    ),
)
