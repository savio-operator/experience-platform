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
from sqlalchemy.dialects.postgresql import JSONB

from app.core.db import metadata

cases = Table(
    "cases",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("booking_id", UUID, ForeignKey("bookings.id"), nullable=False, unique=True),
    Column("state", String(16), nullable=False, server_default="OPEN"),
    Column("assigned_to", UUID, ForeignKey("users.id")),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("resolution_evidence_id", UUID),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint("state IN ('OPEN','ESCALATED','RESOLVED')", name="case_state"),
    CheckConstraint("version > 0", name="case_version"),
    CheckConstraint(
        "state != 'RESOLVED' OR (assigned_to IS NOT NULL "
        "AND resolution_evidence_id IS NOT NULL)",
        name="case_resolution",
    ),
)
case_actions = Table(
    "case_actions",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("case_id", UUID, ForeignKey("cases.id"), nullable=False),
    Column("actor_id", UUID, ForeignKey("users.id"), nullable=False),
    Column("idempotency_key", UUID, nullable=False),
    Column("request", JSONB, nullable=False),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("case_id", "idempotency_key", name="case_action_request_unique"),
)
