"""identity"""

from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_limits",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(
        op.f("ix_auth_limits_reset_at"), "auth_limits", ["reset_at"], unique=False
    )
    op.create_table(
        "identity_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= 5", name="otp_attempts_range"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_table(
        "consents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_consents_customer_id"), "consents", ["customer_id"], unique=False
    )

    op.bulk_insert(
        sa.table("roles", sa.column("id", sa.UUID()), sa.column("name", sa.String())),
        [
            {"id": UUID("e7d1e54e-a330-4e57-9bc3-6997ae75be54"), "name": "customer"},
            {"id": UUID("b2953a23-9b89-41cb-8661-5a54a5de1e58"), "name": "ops_admin"},
        ],
    )
    op.execute("""
        CREATE FUNCTION reject_identity_event_changes() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Identity events are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER identity_events_immutable
        BEFORE UPDATE OR DELETE OR TRUNCATE ON identity_events
        FOR EACH STATEMENT EXECUTE FUNCTION reject_identity_event_changes()
    """)


def downgrade():
    op.drop_index(op.f("ix_consents_customer_id"), table_name="consents")
    op.drop_table("consents")
    op.drop_table("user_roles")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("customers")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("otp_challenges")
    op.drop_table("identity_events")
    op.execute("DROP FUNCTION reject_identity_event_changes()")
    op.drop_index(op.f("ix_auth_limits_reset_at"), table_name="auth_limits")
    op.drop_table("auth_limits")
