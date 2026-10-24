import logging
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.config import get_log_level
from app.main import app


def test_health(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_default_log_level(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert get_log_level() == "INFO"


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_valid_log_level(monkeypatch, level):
    monkeypatch.setenv("LOG_LEVEL", level)
    assert get_log_level() == level


@pytest.mark.parametrize("value", ["", "info", "invalid-private-value"])
def test_invalid_configuration_stops_startup(monkeypatch, value):
    monkeypatch.setenv("LOG_LEVEL", value)
    with pytest.raises(RuntimeError) as error:
        with TestClient(app):
            pytest.fail("Invalid configuration must prevent startup")
    assert str(error.value) == "Invalid LOG_LEVEL configuration"


def test_request_ids_and_logs(monkeypatch, caplog):
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    with caplog.at_level(logging.INFO, logger="app"), TestClient(app) as client:
        first = client.get("/health", headers={"X-Request-ID": "untrusted-id"})
        second = client.get("/health")
    first_id = first.headers["X-Request-ID"]
    second_id = second.headers["X-Request-ID"]
    assert UUID(first_id).version == 4
    assert UUID(second_id).version == 4
    assert first_id != second_id
    messages = [r.getMessage() for r in caplog.records if r.name == "app"]
    assert messages == [
        f"request_id={first_id} status=200",
        f"request_id={second_id} status=200",
    ]
