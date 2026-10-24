from sqlalchemy import (
    UUID,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    func,
)

from app.core.db import metadata

services = Table(
    "services",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("vendor_id", UUID, ForeignKey("vendors.id"), nullable=False, index=True),
    Column("name", String(200), nullable=False),
    Column("description", String(4000)),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint("length(trim(name)) > 0", name="service_name_not_blank"),
)
