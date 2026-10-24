from sqlalchemy import UUID, Boolean, Column, DateTime, ForeignKey, String, Table, func

from app.core.db import metadata

customers = Table(
    "customers",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("user_id", UUID, ForeignKey("users.id"), unique=True, nullable=False),
)
consents = Table(
    "consents",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("customer_id", UUID, ForeignKey("customers.id"), nullable=False, index=True),
    Column("purpose", String(100), nullable=False),
    Column("version", String(100), nullable=False),
    Column("granted", Boolean, nullable=False),
    Column(
        "recorded_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
)
