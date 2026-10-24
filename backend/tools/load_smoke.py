"""Bounded localhost smoke load; no credentials or mutations."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener
from uuid import UUID


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def run(base="http://127.0.0.1:8000"):
    url = urlsplit(base)
    if (
        os.environ.get("APP_ENV") != "test"
        or url.scheme != "http"
        or url.hostname != "127.0.0.1"
        or url.username
        or url.password
        or url.path
        or url.query
        or url.fragment
    ):
        raise ValueError("Smoke load requires test mode and a localhost origin")

    def request(index):
        health = index < 60
        path = "/health" if health else "/ops/queues/payment-review"
        start = time.monotonic()
        opener = build_opener(ProxyHandler({}), NoRedirect())
        try:
            response = opener.open(base + path, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            expected = 200 if health else 401
            if response.status != expected:
                raise RuntimeError("Unexpected smoke response status")
            if response.headers.get("Cache-Control") != "no-store":
                raise RuntimeError("Missing cache protection")
            UUID(response.headers["X-Request-ID"])
            body = json.loads(response.read(4096))
            if body != (
                {"status": "ok"} if health else {"detail": "Authentication required"}
            ):
                raise RuntimeError("Unexpected smoke response body")
        return time.monotonic() - start

    with ThreadPoolExecutor(max_workers=8) as pool:
        timings = sorted(pool.map(request, range(80)))
    print(
        f"Load smoke passed: 80 requests, concurrency 8, "
        f"p95={timings[75]:.3f}s, max={max(timings):.3f}s; "
        "local smoke only, not a production capacity/SLO result"
    )


if __name__ == "__main__":
    try:
        run()
    except Exception:
        raise SystemExit("Load smoke failed; response details withheld") from None
