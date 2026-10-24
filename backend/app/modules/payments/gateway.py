"""Internal normalized contract, not a provider wire protocol."""

from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field

from app.modules.pricing.service import Money, StrictModel


class Observation(StrictModel):
    payment_id: UUID
    amount_paise: Money
    currency: Literal["INR"]
    state: Literal["PENDING", "FAILED", "SUCCEEDED"]


class Event(Observation):
    event_key: str = Field(strict=True, min_length=1, max_length=128)


class GatewayDisabled(Exception):
    pass


class InvalidSignature(Exception):
    pass


class Gateway(Protocol):
    def require_enabled(self) -> None: ...
    async def create(
        self, *, payment_id: UUID, amount_paise: int, currency: str
    ) -> Observation: ...
    async def lookup(self, *, payment_id: UUID) -> Observation | None: ...
    async def verify_webhook(self, body: bytes, headers: dict) -> Event: ...


class DisabledGateway:
    def require_enabled(self):
        raise GatewayDisabled

    async def create(self, **kwargs):
        raise GatewayDisabled

    async def lookup(self, **kwargs):
        raise GatewayDisabled

    async def verify_webhook(self, *args):
        raise GatewayDisabled


def get_gateway():
    # No environment switch, key lookup or live SDK. Fixtures exist only in tests.
    return DisabledGateway()
