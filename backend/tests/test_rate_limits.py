from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import select, text

from app.core.config import load_settings
from app.modules.identity import service
from app.modules.identity.models import auth_limits


def test_email_cooldown_and_retry_header(client, request_code, db):
    request_code()
    response = client.post("/auth/otp/request", json={"email": "CUSTOMER@example.com"})
    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= 60
    with db.begin() as connection:
        connection.execute(
            text("UPDATE auth_limits SET reset_at = now() - interval '1 second'")
        )
    assert (
        client.post(
            "/auth/otp/request", json={"email": "customer@example.com"}
        ).status_code
        == 202
    )


def test_hourly_email_limit_survives_minute_reset(client, db):
    key = load_settings().otp_hash_key
    minute_key = service.digest(key, "limit:send-minute:customer@example.com")
    for _ in range(5):
        assert (
            client.post(
                "/auth/otp/request", json={"email": "customer@example.com"}
            ).status_code
            == 202
        )
        with db.begin() as connection:
            connection.execute(
                auth_limits.update()
                .where(auth_limits.c.key == minute_key)
                .values(reset_at=service_time_past(connection))
            )
    assert (
        client.post(
            "/auth/otp/request", json={"email": "customer@example.com"}
        ).status_code
        == 429
    )


def service_time_past(connection):
    return connection.scalar(text("SELECT now() - interval '1 second'"))


def test_send_ip_limit_ignores_forwarded_headers(client):
    for i in range(20):
        response = client.post(
            "/auth/otp/request", json={"email": f"person{i}@example.com"}
        )
        assert response.status_code == 202
    response = client.post(
        "/auth/otp/request",
        json={"email": "new@example.com"},
        headers={"X-Forwarded-For": "198.51.100.20"},
    )
    assert response.status_code == 429


def test_verification_ip_limit(client):
    body = {"challenge_id": str(uuid4()), "code": "000000"}
    for _ in range(30):
        assert client.post("/auth/otp/verify", json=body).status_code == 400
    assert client.post("/auth/otp/verify", json=body).status_code == 429


def test_concurrent_counters_across_engines(db):
    from app.core.db import make_engine

    settings = load_settings()
    second_engine = make_engine(settings.database_url)
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(
                pool.map(
                    lambda i: service.throttle(
                        db if i % 2 else second_engine,
                        settings.otp_hash_key,
                        "verify",
                        "198.51.100.21",
                    ),
                    range(40),
                )
            )
        assert sum(result == 0 for result in results) == 30
        assert sum(result > 0 for result in results) == 10
        with db.connect() as connection:
            stored = connection.execute(select(auth_limits)).mappings().one()
            assert stored["count"] == 31
            assert "198.51.100.21" not in stored["key"]
    finally:
        second_engine.dispose()


def test_simultaneous_send_allows_only_one(client):
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    "/auth/otp/request", json={"email": "same@example.com"}
                ),
                range(6),
            )
        )
    assert sum(r.status_code == 202 for r in responses) == 1
    assert sum(r.status_code == 429 for r in responses) == 5


def test_session_endpoint_is_throttled(client):
    for _ in range(120):
        assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me").status_code == 429


def test_blocked_ip_does_not_create_unbounded_email_counters(db):
    key = load_settings().otp_hash_key
    for i in range(20):
        assert (
            service.throttle(db, key, "request", "192.0.2.1", f"user{i}@example.com")
            == 0
        )
    with db.connect() as connection:
        before = len(connection.execute(select(auth_limits)).all())
    assert service.throttle(db, key, "request", "192.0.2.1", "new@example.com") > 0
    with db.connect() as connection:
        assert len(connection.execute(select(auth_limits)).all()) == before
