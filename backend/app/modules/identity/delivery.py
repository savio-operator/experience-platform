"""No live delivery and no code retrieval facility in this build."""

from fastapi import Request


class LocalDiscardDelivery:
    def __init__(self, environment: str):
        if environment not in {"local", "test"}:
            raise RuntimeError(
                "Development delivery is unavailable in this environment"
            )

    def send(self, email: str, code: str) -> None:
        # Intentionally discard: never log, persist, or return the code.
        pass


def get_delivery(request: Request):
    return request.app.state.delivery
