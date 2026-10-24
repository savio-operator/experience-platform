from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

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
                "TRUNCATE payments, payment_events, bookings, booking_components, "
                "sessions, user_roles, "
                "consents, customers, users, "
                "otp_challenges, auth_limits, slot_offers, holds, "
                "inventory_slots, services, vendors"
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


@pytest.fixture
def setup(ops):
    client, actor = ops
    now = datetime.now(UTC)
    search = dict(
        kind="date",
        starts_after=now.isoformat(),
        ends_before=(now + timedelta(days=1)).isoformat(),
        quantity=1,
        budget_paise=1000,
        requirements=[],
    )
    vendor = client.post("/ops/vendors", json={"name": "Synthetic"}).json()["id"]

    def add(price=100, facts=None, service_id=None, offset=0, capacity=2):
        if service_id is None:
            service_id = client.post(
                "/ops/services", json={"vendor_id": vendor, "name": "Synthetic option"}
            ).json()["id"]
        slot_body = dict(
            service_id=service_id,
            capacity=capacity,
            starts_at=(now + timedelta(hours=2 + offset)).isoformat(),
            ends_at=(now + timedelta(hours=3 + offset)).isoformat(),
            release_at=(now + timedelta(hours=1)).isoformat(),
        )
        slot = client.post("/ops/inventory/slots", json=slot_body).json()
        path = f"/ops/inventory/slots/{slot['id']}"
        assert (
            client.patch(
                path + "/availability",
                json={
                    "state": "AVAILABLE_VERIFIED",
                    "verified_until": slot_body["release_at"],
                },
            ).status_code
            == 200
        )
        offer = dict(
            source_id=str(uuid4()),
            verified_until=slot_body["release_at"],
            location="Kochi",
            intents=["date"],
            unit_price_paise=price,
            unit_cost_paise=0,
            fees=[],
            taxes=[],
            minimum_margin_paise=0,
            facts=facts or [],
        )
        response = client.put(path + "/offer", json=offer)
        assert response.status_code == 200, response.text
        return slot, offer

    return client, actor, search, add


@pytest.fixture
def candidate(setup):
    client, actor, search, add = setup
    slot, offer = add(100, capacity=1)
    body = dict(
        slot_id=slot["id"],
        idempotency_key=str(uuid4()),
        kind="date",
        quantity=1,
        budget_paise=1000,
        expected_total_paise=100,
        expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        requirements=[],
    )
    return client, actor, slot, offer, body
