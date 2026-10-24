"""cases"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("audit_resource_type", "audit_events", type_="check")
    op.create_check_constraint(
        "audit_resource_type",
        "audit_events",
        "resource_type IN ('vendor','service','inventory_slot','hold',"
        "'booking','component','payment','notification','case')",
    )
    op.create_table(
        "cases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(length=16), server_default="OPEN", nullable=False),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("resolution_evidence_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state != 'RESOLVED' OR (assigned_to IS NOT NULL "
            "AND resolution_evidence_id IS NOT NULL)",
            name="case_resolution",
        ),
        sa.CheckConstraint(
            "state IN ('OPEN','ESCALATED','RESOLVED')", name="case_state"
        ),
        sa.CheckConstraint("version > 0", name="case_version"),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
    )
    op.create_table(
        "case_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("request", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "case_id", "idempotency_key", name="case_action_request_unique"
        ),
    )

    op.execute("""
        CREATE TRIGGER case_actions_immutable
        BEFORE UPDATE OR DELETE ON case_actions
        FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_event_changes()
    """)


def downgrade():
    # Retain audit vocabulary for immutable historical events.
    op.drop_table("case_actions")
    op.drop_table("cases")
