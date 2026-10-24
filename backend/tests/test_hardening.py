import pytest

from tools import load_smoke, recovery


@pytest.mark.parametrize(
    "origin",
    [
        "https://127.0.0.1:8000",
        "http://example.com",
        "http://user@127.0.0.1",
        "http://127.0.0.1/path",
        "http://127.0.0.1?key=value",
        "http://127.0.0.1#fragment",
    ],
)
def test_load_rejects_nonlocal_or_ambiguous_targets(monkeypatch, origin):
    monkeypatch.setenv("APP_ENV", "test")
    with pytest.raises(ValueError):
        load_smoke.run(origin)


def test_load_refuses_non_test_mode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    with pytest.raises(ValueError):
        load_smoke.run()


def test_load_does_not_follow_redirects():
    assert load_smoke.NoRedirect().redirect_request(None) is None


@pytest.mark.parametrize(
    "project", ["production", "experience-../", "experience-test;evil"]
)
def test_recovery_rejects_unsafe_projects(project):
    with pytest.raises(RuntimeError):
        recovery.verify(project)


def test_recovery_refuses_local_database(monkeypatch):
    class Local:
        environment = "local"

    monkeypatch.setattr(recovery, "load_settings", lambda: Local())
    with pytest.raises(RuntimeError):
        recovery.verify("experience-check")


@pytest.mark.parametrize("status", [200, 302, 500])
def test_load_detects_incorrect_status_or_body(monkeypatch, status):
    class Response:
        headers = {
            "Cache-Control": "no-store",
            "X-Request-ID": "00000000-0000-0000-0000-000000000001",
        }

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            return b'{"wrong":"body"}'

    response = Response()
    response.status = status

    class Opener:
        def open(self, *args, **kwargs):
            return response

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setattr(load_smoke, "build_opener", lambda *args: Opener())
    with pytest.raises(RuntimeError):
        load_smoke.run()
