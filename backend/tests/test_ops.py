from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import DBAPIError

from app.modules.audit import service as audit
from app.modules.audit.models import audit_events
from app.modules.catalogue.models import services
from app.modules.identity.models import roles, user_roles, users
from app.modules.vendors import service as vendor_service
from app.modules.vendors.models import vendors


def test_ops_create_edit_and_audit(ops, db, caplog):
    client, actor_id = ops
    response = client.post(
        "/ops/vendors",
        json={"name": " Vendor ", "contact_email": "private@example.com"},
    )
    assert response.status_code == 201
    vendor = response.json()
    assert vendor["name"] == "Vendor"
    vendor_id = UUID(vendor["id"])
    response = client.post(
        "/ops/services", json={"vendor_id": str(vendor_id), "name": "Experience"}
    )
    assert response.status_code == 201
    service_id = UUID(response.json()["id"])
    response = client.patch(
        f"/ops/vendors/{vendor_id}",
        json={"contact_email": None, "terms_notes": "Private terms"},
    )
    assert response.status_code == 200 and response.json()["contact_email"] is None
    response = client.patch(
        f"/ops/services/{service_id}",
        json={"description": "Description", "name": "Revised"},
    )
    assert response.status_code == 200 and response.json()["name"] == "Revised"
    with db.connect() as connection:
        events = (
            connection.execute(
                select(audit_events).where(
                    audit_events.c.resource_id.in_([vendor_id, service_id])
                )
            )
            .mappings()
            .all()
        )
        assert len(events) == 4
        assert all(e["actor_id"] == actor_id for e in events)
        assert {e["action"] for e in events} == {"created", "updated"}
        changed = [e["changed_fields"] for e in events if e["action"] == "updated"]
        assert sorted(["contact_email", "terms_notes"]) in changed
        assert sorted(["description", "name"]) in changed
        assert all(e["created_at"].tzinfo is not None for e in events)
    assert "private@example.com" not in str(events) + caplog.text
    assert "Private terms" not in str(events) + caplog.text


@pytest.mark.parametrize("authenticated", [False, True])
@pytest.mark.parametrize(
    "method,path,body",
    [
        ("post", "/ops/vendors", {"name": "Vendor"}),
        ("post", "/ops/services", {"name": "Service", "vendor_id": str(uuid4())}),
        ("patch", f"/ops/vendors/{uuid4()}", {"name": "Changed"}),
        ("patch", f"/ops/services/{uuid4()}", {"name": "Changed"}),
    ],
)
def test_non_ops_denied(client, login, db, authenticated, method, path, body):
    if authenticated:
        login()
    response = getattr(client, method)(path, json=body, headers={"X-Role": "ops_admin"})
    assert response.status_code == (403 if authenticated else 401)
    with db.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(vendors)) == 0
        assert connection.scalar(select(func.count()).select_from(services)) == 0


@pytest.mark.parametrize(
    "body",
    [
        {"name": " "},
        {"name": "x" * 201},
        {"name": "Valid", "price": 100},
        {"name": "Valid", "contact_email": "not-an-email"},
        {"name": "Valid", "terms_notes": "x" * 4001},
    ],
)
def test_vendor_validation(ops, body):
    response = ops[0].post("/ops/vendors", json=body)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request"}


def test_update_validation_and_missing_records(ops):
    client, _ = ops
    vendor = client.post("/ops/vendors", json={"name": "Vendor"}).json()
    service = client.post(
        "/ops/services", json={"name": "Service", "vendor_id": vendor["id"]}
    ).json()
    for path in (f"/ops/vendors/{vendor['id']}", f"/ops/services/{service['id']}"):
        for body in ({}, {"name": None}, {"name": " "}, {"id": str(uuid4())}):
            assert client.patch(path, json=body).status_code == 422
    assert (
        client.patch(
            f"/ops/services/{service['id']}", json={"vendor_id": str(uuid4())}
        ).status_code
        == 422
    )
    assert (
        client.patch(f"/ops/vendors/{uuid4()}", json={"name": "Missing"}).status_code
        == 404
    )
    assert (
        client.patch(f"/ops/services/{uuid4()}", json={"name": "Missing"}).status_code
        == 404
    )
    assert (
        client.patch("/ops/vendors/not-a-uuid", json={"name": "Invalid"}).status_code
        == 422
    )
    assert (
        client.post(
            "/ops/services", json={"name": "Missing", "vendor_id": str(uuid4())}
        ).status_code
        == 404
    )


def test_foreign_key_enforced(db):
    with pytest.raises(DBAPIError):
        with db.begin() as connection:
            connection.execute(
                insert(services).values(id=uuid4(), vendor_id=uuid4(), name="Invalid")
            )


def test_noop_does_not_audit_or_change_timestamp(ops, db):
    client, _ = ops
    vendor = client.post("/ops/vendors", json={"name": "Vendor"}).json()
    response = client.patch(f"/ops/vendors/{vendor['id']}", json={"name": "Vendor"})
    assert response.json()["updated_at"] == vendor["updated_at"]
    with db.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(audit_events)
                .where(audit_events.c.resource_id == UUID(vendor["id"]))
            )
            == 1
        )


def test_audit_failure_rolls_back_create_and_update(ops, db, monkeypatch):
    client, _ = ops
    vendor = client.post("/ops/vendors", json={"name": "Before"}).json()
    service = client.post(
        "/ops/services", json={"name": "Before", "vendor_id": vendor["id"]}
    ).json()

    def fail(*args):
        raise RuntimeError("private-audit-error")

    monkeypatch.setattr(audit, "record", fail)
    attempts = [
        ("post", "/ops/vendors", {"name": "Failed"}),
        ("post", "/ops/services", {"name": "Failed", "vendor_id": vendor["id"]}),
        ("patch", f"/ops/vendors/{vendor['id']}", {"name": "Failed"}),
        ("patch", f"/ops/services/{service['id']}", {"name": "Failed"}),
    ]
    for method, path, body in attempts:
        response = getattr(client, method)(path, json=body)
        assert (
            response.status_code == 500 and "private-audit-error" not in response.text
        )
    with db.connect() as connection:
        assert connection.execute(select(vendors.c.name)).scalars().all() == ["Before"]
        assert connection.execute(select(services.c.name)).scalars().all() == ["Before"]


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET action='updated'",
        "DELETE FROM audit_events",
        "TRUNCATE audit_events",
    ],
)
def test_audit_is_append_only(db, statement):
    with pytest.raises(DBAPIError):
        with db.begin() as connection:
            connection.execute(text(statement))


def test_role_revocation_effective_immediately(ops, db):
    client, actor = ops
    with db.begin() as connection:
        connection.execute(delete(user_roles).where(user_roles.c.user_id == actor))
    assert client.post("/ops/vendors", json={"name": "Forbidden"}).status_code == 403


def test_concurrent_partial_updates_preserve_other_fields(ops, db):
    client, actor = ops
    vendor = client.post("/ops/vendors", json={"name": "Vendor"}).json()
    values = [{"name": "Updated"}, {"contact_name": "Contact"}]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(
            pool.map(
                lambda fields: vendor_service.update_vendor(
                    db, actor, UUID(vendor["id"]), fields
                ),
                values,
            )
        )
    with db.connect() as connection:
        row = connection.execute(select(vendors)).mappings().one()
        assert row["name"] == "Updated" and row["contact_name"] == "Contact"


def test_migration_preserves_identity_data(db):
    # Only this suite's disposable experience_test database is touched.
    from pathlib import Path

    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.downgrade(config, "0001")
    user_id = uuid4()
    try:
        with db.begin() as connection:
            connection.execute(
                insert(users).values(id=user_id, email="migration@example.com")
            )
        command.upgrade(config, "head")
        with db.connect() as connection:
            assert (
                connection.scalar(select(users.c.email).where(users.c.id == user_id))
                == "migration@example.com"
            )
            assert connection.scalar(select(func.count()).select_from(roles)) == 2
    finally:
        command.upgrade(config, "head")
