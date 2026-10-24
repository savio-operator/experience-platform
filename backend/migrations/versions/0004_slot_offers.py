"""Ops-managed evidence and pricing snapshots for inventory slots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "slot_offers",
        sa.Column(
            "slot_id", sa.UUID(), sa.ForeignKey("inventory_slots.id"), primary_key=True
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_table("slot_offers")
