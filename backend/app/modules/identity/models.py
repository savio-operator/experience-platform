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

roles = Table(
    "roles",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("name", String(32), unique=True, nullable=False),
)
users = Table(
    "users",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("email", String(320), unique=True, nullable=False),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)
user_roles = Table(
    "user_roles",
    metadata,
    Column("user_id", UUID, ForeignKey("users.id"), primary_key=True),
    Column("role_id", UUID, ForeignKey("roles.id"), primary_key=True),
)
otp_challenges = Table(
    "otp_challenges",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("email", String(320), unique=True, nullable=False),
    Column("code_hash", String(64), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("consumed_at", DateTime(timezone=True)),
    CheckConstraint("attempts >= 0 AND attempts <= 5", name="otp_attempts_range"),
)
sessions = Table(
    "sessions",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("user_id", UUID, ForeignKey("users.id"), nullable=False, index=True),
    Column("token_hash", String(64), unique=True, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
)
auth_limits = Table(
    "auth_limits",
    metadata,
    Column("key", String(64), primary_key=True),
    Column("count", Integer, nullable=False),
    Column("reset_at", DateTime(timezone=True), nullable=False, index=True),
)
identity_events = Table(
    "identity_events",
    metadata,
    Column("id", UUID, primary_key=True),
    Column("event", String(40), nullable=False),
    Column("subject_id", UUID, nullable=False),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)
