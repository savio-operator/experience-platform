from uuid import uuid4

from sqlalchemy import func, insert, select, update

from app.modules.audit import service as audit
from app.modules.vendors.models import vendors


def create_vendor(engine, actor_id, values):
    with engine.begin() as connection:
        row = (
            connection.execute(
                insert(vendors).values(id=uuid4(), **values).returning(vendors)
            )
            .mappings()
            .one()
        )
        audit.record(connection, actor_id, "vendor", row["id"], "created", values)
        return dict(row)


def update_vendor(engine, actor_id, vendor_id, values):
    with engine.begin() as connection:
        row = (
            connection.execute(
                select(vendors).where(vendors.c.id == vendor_id).with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            raise LookupError("Vendor not found")
        changed = {name: value for name, value in values.items() if row[name] != value}
        if changed:
            row = (
                connection.execute(
                    update(vendors)
                    .where(vendors.c.id == vendor_id)
                    .values(**changed, updated_at=func.clock_timestamp())
                    .returning(vendors)
                )
                .mappings()
                .one()
            )
            audit.record(connection, actor_id, "vendor", vendor_id, "updated", changed)
        return dict(row)
