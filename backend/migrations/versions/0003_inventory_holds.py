"""inventory_holds"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("audit_resource_type", "audit_events", type_="check")
    op.drop_constraint("audit_action", "audit_events", type_="check")
    op.create_check_constraint(
        "audit_resource_type",
        "audit_events",
        "resource_type IN ('vendor', 'service', 'inventory_slot', 'hold')",
    )
    op.create_check_constraint(
        "audit_action",
        "audit_events",
        "action IN ('created', 'updated', 'unknown', 'unverified', 'verified', "
        "'held', 'unavailable', 'expired', 'released')",
    )
    op.create_table(
        "inventory_slots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("release_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column(
            "state", sa.String(length=32), server_default="UNKNOWN", nullable=False
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('UNKNOWN','AVAILABLE_UNVERIFIED','AVAILABLE_VERIFIED',"
            "'HELD','BOOKING_PENDING','CONFIRMED','UNAVAILABLE','EXPIRED')",
            name="slot_state",
        ),
        sa.CheckConstraint("capacity > 0", name="slot_capacity_positive"),
        sa.CheckConstraint(
            "ends_at > starts_at AND release_at <= starts_at", name="slot_time_order"
        ),
        sa.CheckConstraint(
            "verified_until IS NULL OR (verified_at IS NOT NULL AND "
            "verified_until > verified_at AND verified_until <= release_at)",
            name="slot_verification_window",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service_id", "starts_at", "ends_at", name="slot_exact_window_unique"
        ),
    )
    op.create_index(
        op.f("ix_inventory_slots_service_id"),
        "inventory_slots",
        ["service_id"],
        unique=False,
    )
    op.create_table(
        "holds",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slot_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "state", sa.String(length=16), server_default="ACTIVE", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('ACTIVE','RELEASED','EXPIRED')", name="hold_state"
        ),
        sa.CheckConstraint("quantity > 0", name="hold_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["inventory_slots.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_id", "idempotency_key", name="hold_request_unique"),
    )
    op.create_index(op.f("ix_holds_slot_id"), "holds", ["slot_id"], unique=False)


def downgrade():
    # Keep the wider audit vocabulary to preserve immutable historical events.
    op.drop_index(op.f("ix_holds_slot_id"), table_name="holds")
    op.drop_table("holds")
    op.drop_index(op.f("ix_inventory_slots_service_id"), table_name="inventory_slots")
    op.drop_table("inventory_slots")
