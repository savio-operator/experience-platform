"""bookings"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("audit_resource_type", "audit_events", type_="check")
    op.create_check_constraint(
        "audit_resource_type",
        "audit_events",
        "resource_type IN ('vendor','service','inventory_slot','hold',"
        "'booking','component')",
    )
    op.drop_constraint("audit_action", "audit_events", type_="check")
    op.create_check_constraint(
        "audit_action",
        "audit_events",
        "action IN ('created','updated','unknown','unverified','verified','held',"
        "'unavailable','expired','released','confirmed','failed')",
    )
    op.drop_constraint("hold_state", "holds", type_="check")
    op.create_check_constraint(
        "hold_state", "holds", "state IN ('ACTIVE','RELEASED','EXPIRED','CONFIRMED')"
    )
    op.create_table(
        "bookings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("slot_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("request", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "price_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("total_paise", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('VENDOR_CONFIRMATION_PENDING','CONFIRMED','FAILED')",
            name="booking_state",
        ),
        sa.CheckConstraint("total_paise >= 0", name="booking_total_nonnegative"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["inventory_slots.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id", "idempotency_key", name="booking_request_unique"
        ),
    )
    op.create_index(
        op.f("ix_bookings_customer_id"), "bookings", ["customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_bookings_expires_at"), "bookings", ["expires_at"], unique=False
    )
    op.create_table(
        "booking_components",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("hold_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("vendor_confirmation_id", sa.UUID(), nullable=True),
        sa.Column("confirmed_by", sa.UUID(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state != 'CONFIRMED' OR (vendor_confirmation_id IS NOT NULL "
            "AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
            name="component_confirmation_required",
        ),
        sa.CheckConstraint(
            "state IN ('VENDOR_CONFIRMATION_PENDING','CONFIRMED','EXPIRED','REJECTED')",
            name="component_state",
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["hold_id"],
            ["holds.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
        sa.UniqueConstraint("hold_id"),
    )

    op.execute("""
        CREATE FUNCTION require_booking_confirmation() RETURNS trigger AS $$
        DECLARE target uuid;
        BEGIN
            IF TG_TABLE_NAME = 'bookings' THEN
                target := COALESCE(NEW.id, OLD.id);
            ELSE
                target := COALESCE(NEW.booking_id, OLD.booking_id);
            END IF;
            IF EXISTS (SELECT 1 FROM bookings WHERE id=target AND state='CONFIRMED')
            AND (NOT EXISTS (SELECT 1 FROM booking_components WHERE booking_id=target)
                 OR EXISTS (SELECT 1 FROM booking_components
                            WHERE booking_id=target AND state!='CONFIRMED')) THEN
                RAISE EXCEPTION 'Booking requires confirmed components';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
    """)
    for table in ("bookings", "booking_components"):
        op.execute(f"""CREATE CONSTRAINT TRIGGER require_confirmation
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION require_booking_confirmation()""")


def downgrade():
    # Never lose durable capacity reservations by downgrading to old hold semantics.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM holds WHERE state='CONFIRMED') THEN
            RAISE EXCEPTION 'Cannot downgrade with confirmed reservations';
        END IF;
    END $$""")
    for table in ("booking_components", "bookings"):
        op.execute(f"DROP TRIGGER require_confirmation ON {table}")
    op.execute("DROP FUNCTION require_booking_confirmation()")
    op.drop_constraint("hold_state", "holds", type_="check")
    op.create_check_constraint(
        "hold_state", "holds", "state IN ('ACTIVE','RELEASED','EXPIRED')"
    )
    # Retain expanded audit vocabulary for immutable historical records.
    op.drop_table("booking_components")
    op.drop_index(op.f("ix_bookings_expires_at"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_customer_id"), table_name="bookings")
    op.drop_table("bookings")
