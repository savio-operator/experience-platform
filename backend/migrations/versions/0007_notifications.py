"""notifications"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("audit_resource_type", "audit_events", type_="check")
    op.create_check_constraint(
        "audit_resource_type",
        "audit_events",
        "resource_type IN ('vendor','service','inventory_slot','hold',"
        "'booking','component','payment','notification')",
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=True),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False),
        sa.Column(
            "state", sa.String(length=16), server_default="PENDING", nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_id", sa.UUID(), nullable=True),
        sa.Column("receipt_id", sa.UUID(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('BOOKING_CONFIRMED','BOOKING_FAILED','REMINDER',"
            "'PAYMENT_SUCCEEDED','PAYMENT_FAILED')",
            name="notification_kind",
        ),
        sa.CheckConstraint(
            "state != 'SENT' OR (receipt_id IS NOT NULL AND sent_at IS NOT NULL)",
            name="notification_receipt",
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','SENDING','SENT','FAILED','CANCELLED')",
            name="notification_state",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= 3", name="notification_attempts"
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        op.f("ix_notifications_customer_id"),
        "notifications",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_due_at"), "notifications", ["due_at"], unique=False
    )


def downgrade():
    # Preserve expanded audit vocabulary for immutable historical records.
    op.drop_index(op.f("ix_notifications_due_at"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_customer_id"), table_name="notifications")
    op.drop_table("notifications")
