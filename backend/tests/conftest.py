from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, text

from app.core.config import load_settings
from app.core.db import make_engine
from app.main import create_app
from app.modules.identity.delivery import get_delivery
from app.modules.identity.models import roles, user_roles


@pytest.fixture(scope="session")
def engine():
    settings = load_settings()
    if settings.environment != "test":
        pytest.fail(
            "Tests require APP_ENV=test and a disposable experience_test database"
        )
    engine = make_engine(settings.database_url)
    with engine.connect() as connection:
        if connection.scalar(text("SELECT current_database()")) != "experience_test":
            pytest.fail("Refusing to reset a non-test database")
        if not connection.scalar(text("SELECT version_num FROM alembic_version")):
            pytest.fail("Apply migrations explicitly before testing")
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    # Reset only the validated test database; audit records stay append-only.
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE sessions, user_roles, consents, customers, users, "
                "otp_challenges, auth_limits, holds, inventory_slots, services, vendors"
            )
        )
    return engine


class RecordingDelivery:
    """Test-only transport: never imported into or copied to the runtime image."""

    def __init__(self):
        self.messages = []

    def send(self, email, code):
        self.messages.append((email, code))


@pytest.fixture
def delivery():
    return RecordingDelivery()


@pytest.fixture
def application(db, delivery):
    application = create_app()
    application.dependency_overrides[get_delivery] = lambda: delivery
    return application


@pytest.fixture
def client(application):
    with TestClient(application) as client:
        yield client


@pytest.fixture
def request_code(client, delivery):
    def request(email="customer@example.com"):
        response = client.post("/auth/otp/request", json={"email": email})
        assert response.status_code == 202
        return response.json()["challenge_id"], delivery.messages[-1][1]

    return request


@pytest.fixture
def login(client, request_code):
    def sign_in(email="customer@example.com"):
        challenge, code = request_code(email)
        response = client.post(
            "/auth/otp/verify", json={"challenge_id": challenge, "code": code}
        )
        assert response.status_code == 204
        return client.get("/auth/me").json()

    return sign_in


@pytest.fixture
def ops(client, login, db):
    actor = login("ops@example.com")
    with db.begin() as connection:
        role_id = connection.scalar(
            select(roles.c.id).where(roles.c.name == "ops_admin")
        )
        connection.execute(
            insert(user_roles).values(user_id=UUID(actor["id"]), role_id=role_id)
        )
    return client, UUID(actor["id"])
