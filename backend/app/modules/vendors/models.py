from sqlalchemy import UUID, CheckConstraint, Column, DateTime, String, Table, func

from app.core.db import metadata

vendors = Table(
    "vendors",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("name", String(200), nullable=False),
    Column("contact_name", String(200)),
    Column("contact_email", String(320)),
    Column("contact_phone", String(32)),
    Column("terms_notes", String(4000)),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint("length(trim(name)) > 0", name="vendor_name_not_blank"),
)
