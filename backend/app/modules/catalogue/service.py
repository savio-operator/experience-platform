from uuid import uuid4

from sqlalchemy import func, insert, select, update

from app.modules.audit import service as audit
from app.modules.catalogue.models import services
from app.modules.vendors.models import vendors


def create_service(engine, actor_id, values):
    with engine.begin() as connection:
        if (
            connection.scalar(
                select(vendors.c.id).where(vendors.c.id == values["vendor_id"])
            )
            is None
        ):
            raise LookupError("Vendor not found")
        row = (
            connection.execute(
                insert(services).values(id=uuid4(), **values).returning(services)
            )
            .mappings()
            .one()
        )
        audit.record(connection, actor_id, "service", row["id"], "created", values)
        return dict(row)


def update_service(engine, actor_id, service_id, values):
    with engine.begin() as connection:
        row = (
            connection.execute(
                select(services).where(services.c.id == service_id).with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            raise LookupError("Service not found")
        changed = {name: value for name, value in values.items() if row[name] != value}
        if changed:
            row = (
                connection.execute(
                    update(services)
                    .where(services.c.id == service_id)
                    .values(**changed, updated_at=func.clock_timestamp())
                    .returning(services)
                )
                .mappings()
                .one()
            )
            audit.record(
                connection, actor_id, "service", service_id, "updated", changed
            )
        return dict(row)
