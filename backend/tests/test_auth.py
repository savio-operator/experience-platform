import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.config import load_settings
from app.main import create_app
from app.modules.customers.models import consents, customers
from app.modules.identity import service
from app.modules.identity.delivery import LocalDiscardDelivery
from app.modules.identity.models import identity_events, otp_challenges, sessions, users


def test_signup_and_secret_storage(client, request_code, db, caplog):
    caplog.set_level(logging.INFO, logger="app")
    challenge, code = request_code("Customer@EXAMPLE.COM")
    with db.connect() as connection:
        row = connection.execute(select(otp_challenges)).mappings().one()
        assert row["code_hash"] == service.digest(
            load_settings().otp_hash_key, f"otp:{challenge}:{code}"
        )
        assert row["code_hash"] != code
        remaining = row["expires_at"] - connection.scalar(
            select(func.clock_timestamp())
        )
        assert timedelta(minutes=4) < remaining <= timedelta(minutes=5)
        assert connection.scalar(select(func.count()).select_from(users)) == 0
    response = client.post(
        "/auth/otp/verify", json={"challenge_id": challenge, "code": code}
    )
    assert response.status_code == 204 and response.content == b""
    token = client.cookies[service.COOKIE_NAME]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert "max-age=86400" in cookie and "domain=" not in cookie
    identity = client.get("/auth/me").json()
    assert identity["email"] == "customer@example.com"
    assert identity["roles"] == ["customer"]
    UUID(identity["id"])
    UUID(identity["customer_id"])
    with db.connect() as connection:
        assert connection.scalar(select(sessions.c.token_hash)) == service.token_hash(
            token
        )
        assert connection.scalar(select(func.count()).select_from(customers)) == 1
        assert connection.scalar(select(func.count()).select_from(consents)) == 0
        names = set(connection.execute(select(identity_events.c.event)).scalars())
        assert {
            "otp_requested",
            "otp_verified",
            "customer_registered",
            "session_created",
        } <= names
    app_logs = " ".join(r.getMessage() for r in caplog.records if r.name == "app")
    for private in (
        code,
        token,
        "customer@example.com",
        load_settings().otp_hash_key.decode(),
    ):
        assert private not in app_logs


def test_five_failed_attempts_are_persisted(client, request_code, db):
    challenge, code = request_code()
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        response = client.post(
            "/auth/otp/verify", json={"challenge_id": challenge, "code": wrong}
        )
        assert response.status_code == 400
    assert (
        client.post(
            "/auth/otp/verify", json={"challenge_id": challenge, "code": code}
        ).status_code
        == 400
    )
    with db.connect() as connection:
        assert connection.scalar(select(otp_challenges.c.attempts)) == 5
        assert connection.scalar(select(func.count()).select_from(users)) == 0


def test_expired_and_unknown_codes(client, request_code, db):
    challenge, code = request_code()
    with db.begin() as connection:
        connection.execute(
            update(otp_challenges).values(expires_at=func.now() - timedelta(seconds=1))
        )
    for identifier in (challenge, str(uuid4())):
        response = client.post(
            "/auth/otp/verify", json={"challenge_id": identifier, "code": code}
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid or expired code"}


def test_resend_invalidates_previous_challenge(client, request_code, db):
    old_id, old_code = request_code()
    with db.begin() as connection:
        connection.execute(
            text("UPDATE auth_limits SET reset_at = now() - interval '1 second'")
        )
    new_id, new_code = request_code()
    assert old_id != new_id
    assert (
        client.post(
            "/auth/otp/verify", json={"challenge_id": old_id, "code": old_code}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/auth/otp/verify", json={"challenge_id": new_id, "code": new_code}
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/auth/otp/verify", json={"challenge_id": new_id, "code": new_code}
        ).status_code
        == 400
    )


def test_concurrent_verification_creates_exactly_one_session(request_code, db):
    challenge, code = request_code()
    key = load_settings().otp_hash_key
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(
                lambda _: service.verify_otp(db, key, UUID(challenge), code), range(6)
            )
        )
    assert sum(result is not None for result in results) == 1
    with db.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(sessions)) == 1
        assert connection.scalar(select(func.count()).select_from(users)) == 1


def test_login_rotates_session_and_reuses_account(client, login, db):
    first = login()
    old_token = client.cookies[service.COOKIE_NAME]
    with db.begin() as connection:
        connection.execute(
            text("UPDATE auth_limits SET reset_at = now() - interval '1 second'")
        )
    second = login("CUSTOMER@example.com")
    assert first["id"] == second["id"]
    assert old_token != client.cookies[service.COOKIE_NAME]
    assert service.get_identity(db, old_token) is None
    with db.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(users)) == 1


def test_logout_revokes_session_idempotently(client, login, db):
    login()
    token = client.cookies[service.COOKIE_NAME]
    assert client.post("/auth/logout", json={}).status_code == 204
    assert service.COOKIE_NAME not in client.cookies
    assert service.get_identity(db, token) is None
    client.cookies.set(service.COOKIE_NAME, token)
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/logout", json={}).status_code == 204


def test_session_expiry_and_forgery(client, login, db):
    login()
    with db.begin() as connection:
        connection.execute(
            update(sessions).values(expires_at=func.now() - timedelta(seconds=1))
        )
    assert client.get("/auth/me").status_code == 401
    client.cookies.clear()
    client.cookies.set(service.COOKIE_NAME, "forged-token")
    assert client.get("/auth/me").status_code == 401


@pytest.mark.parametrize("mode", [None, "production", "staging", "unknown"])
def test_unsupported_environments_fail_before_engine_creation(monkeypatch, mode):
    if mode is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", mode)

    def forbidden(*args):
        pytest.fail("Must reject environment before creating a DB engine")

    monkeypatch.setattr("app.main.make_engine", forbidden)
    with pytest.raises(RuntimeError, match="APP_ENV"):
        with TestClient(create_app()):
            pytest.fail("Must not start")
    with pytest.raises(RuntimeError):
        LocalDiscardDelivery(mode)


@pytest.mark.parametrize(
    "variable,value",
    [
        (
            "DATABASE_URL",
            "postgresql+psycopg://user:private@remote.example/experience_test",
        ),
        ("DATABASE_URL", "postgresql+psycopg://user:private@localhost/production"),
        ("DATABASE_URL", "sqlite:///experience_test"),
        ("OTP_HASH_KEY", "private-invalid-key"),
    ],
)
def test_configuration_failures_hide_values(monkeypatch, variable, value):
    monkeypatch.setenv(variable, value)
    with pytest.raises(RuntimeError) as error:
        load_settings()
    assert variable in str(error.value) and value not in str(error.value)


def test_local_delivery_discards_without_storage_or_output(capsys, caplog):
    adapter = LocalDiscardDelivery("local")
    adapter.send("private@example.com", "012345")
    assert adapter.__dict__ == {}
    assert not capsys.readouterr().out and not caplog.records


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email-private-value"},
        {"email": "customer@example.com", "role": "ops_admin"},
    ],
)
def test_invalid_input_is_not_echoed(client, payload):
    response = client.post("/auth/otp/request", json=payload)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request"}


def test_invalid_code_input_is_not_echoed(client):
    response = client.post(
        "/auth/otp/verify", json={"challenge_id": str(uuid4()), "code": "1234567"}
    )
    assert response.status_code == 422 and "1234567" not in response.text


@pytest.mark.parametrize(
    "headers",
    [
        {"origin": "https://untrusted.example"},
        {"origin": "null"},
        {"sec-fetch-site": "cross-site"},
    ],
)
def test_cross_origin_requests_rejected(client, headers):
    assert (
        client.post(
            "/auth/otp/request", json={"email": "user@example.com"}, headers=headers
        ).status_code
        == 403
    )


def test_form_requests_rejected(client):
    assert (
        client.post("/auth/otp/request", data={"email": "user@example.com"}).status_code
        == 403
    )


def test_delivery_failure_rolls_back_and_hides_details(
    client, delivery, db, monkeypatch, caplog
):
    def fail(email, code):
        raise RuntimeError("private-provider-error")

    monkeypatch.setattr(delivery, "send", fail)
    response = client.post("/auth/otp/request", json={"email": "user@example.com"})
    assert response.status_code == 500
    assert "private-provider-error" not in response.text + caplog.text
    with db.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(otp_challenges)) == 0


def test_database_failure_is_closed_and_sanitized(
    client, application, monkeypatch, caplog
):
    def fail():
        raise OperationalError(
            "private-query",
            {"password": "private-password"},
            Exception("private-error"),
        )

    monkeypatch.setattr(application.state.engine, "begin", fail)
    response = client.post("/auth/otp/request", json={"email": "user@example.com"})
    assert response.status_code == 503
    assert "private-" not in response.text + caplog.text


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE identity_events SET event = 'tampered'",
        "DELETE FROM identity_events",
        "TRUNCATE identity_events",
    ],
)
def test_identity_events_are_append_only(db, statement):
    with pytest.raises(DBAPIError):
        with db.begin() as connection:
            connection.execute(text(statement))


def test_request_responses_do_not_reveal_existing_accounts(client, login, db, delivery):
    login()
    with db.begin() as connection:
        connection.execute(
            text("UPDATE auth_limits SET reset_at = now() - interval '1 second'")
        )
    existing = client.post("/auth/otp/request", json={"email": "customer@example.com"})
    new = client.post("/auth/otp/request", json={"email": "new@example.com"})
    assert existing.status_code == new.status_code == 202
    assert set(existing.json()) == set(new.json()) == {"status", "challenge_id"}
    assert existing.json()["status"] == new.json()["status"] == "accepted"
    assert delivery.messages[-1][1] not in new.text
