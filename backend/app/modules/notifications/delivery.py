"""No channel, provider, message templates or credentials enabled."""

from typing import Protocol
from uuid import UUID


class DeliveryDisabled(Exception):
    pass


class Delivery(Protocol):
    def require_enabled(self) -> None: ...
    async def send(
        self,
        *,
        notification_id: UUID,
        recipient_id: UUID,
        booking_id: UUID,
        payment_id: UUID | None,
        kind: str,
    ) -> UUID: ...


class DisabledDelivery:
    def require_enabled(self):
        raise DeliveryDisabled

    async def send(self, **kwargs):
        raise DeliveryDisabled


def get_delivery():
    return DisabledDelivery()
