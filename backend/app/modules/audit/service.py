from uuid import uuid4

from sqlalchemy import insert

from app.modules.audit.models import audit_events


def record(connection, actor_id, resource_type, resource_id, action, changed_fields):
    connection.execute(
        insert(audit_events).values(
            id=uuid4(),
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            changed_fields=sorted(changed_fields),
        )
    )
