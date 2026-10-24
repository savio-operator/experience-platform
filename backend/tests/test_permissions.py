from uuid import UUID, uuid4

from fastapi import Depends
from sqlalchemy import delete, insert, select

from app.api.auth import current_identity, require_owner, require_role
from app.modules.identity.models import roles, user_roles


def test_role_checks_use_database_and_reject_client_roles(
    application, client, login, db
):
    @application.get("/test/admin")
    def admin(identity=Depends(require_role("ops_admin"))):
        return {"allowed": True}

    assert client.get("/test/admin").status_code == 401
    identity = login()
    assert client.get("/test/admin", headers={"X-Role": "ops_admin"}).status_code == 403
    with db.begin() as connection:
        role_id = connection.scalar(
            select(roles.c.id).where(roles.c.name == "ops_admin")
        )
        connection.execute(
            insert(user_roles).values(user_id=UUID(identity["id"]), role_id=role_id)
        )
    assert client.get("/test/admin").status_code == 200
    with db.begin() as connection:
        connection.execute(delete(user_roles).where(user_roles.c.role_id == role_id))
    assert client.get("/test/admin").status_code == 403


def test_ownership_is_separate_from_roles(application, client, login):
    @application.get("/test/owner/{owner_id}")
    def owned(owner_id: UUID, identity=Depends(current_identity)):
        require_owner(identity, owner_id)
        return {"allowed": True}

    identity = login()
    assert client.get(f"/test/owner/{identity['id']}").status_code == 200
    assert client.get(f"/test/owner/{uuid4()}").status_code == 403


def test_no_admin_or_delivery_endpoints(client):
    for path in ("/test/admin", "/auth/otp/latest", "/auth/roles", "/admin"):
        assert client.get(path).status_code == 404
