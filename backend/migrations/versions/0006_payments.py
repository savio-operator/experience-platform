"""payments"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("audit_resource_type", "audit_events", type_="check")
    op.create_check_constraint(
        "audit_resource_type",
        "audit_events",
        "resource_type IN ('vendor','service','inventory_slot','hold',"
        "'booking','component','payment')",
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("review_reason", sa.String(length=32), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("currency = 'INR'", name="payment_currency"),
        sa.CheckConstraint(
            "review_reason IS NULL OR review_reason IN "
            "('GATEWAY_UNKNOWN','BOOKING_FAILED')",
            name="payment_review_reason",
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','FAILED','SUCCEEDED')", name="payment_state"
        ),
        sa.CheckConstraint("amount_paise >= 0", name="payment_amount_nonnegative"),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
        sa.UniqueConstraint(
            "customer_id", "idempotency_key", name="payment_request_unique"
        ),
    )
    op.create_table(
        "payment_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key"),
    )


def downgrade():
    # Preserve the expanded vocabulary for immutable historical audit records.
    op.drop_table("payment_events")
    op.drop_table("payments")
