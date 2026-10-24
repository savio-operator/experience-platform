from sqlalchemy import UUID, Column, DateTime, ForeignKey, Table, func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.db import metadata

slot_offers = Table(
    "slot_offers",
    metadata,
    Column("slot_id", UUID, ForeignKey("inventory_slots.id"), primary_key=True),
    Column("payload", JSONB, nullable=False),
    Column("updated_by", UUID, ForeignKey("users.id"), nullable=False),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)
