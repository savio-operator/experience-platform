import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.api.auth import current_identity, enforce_limit
from app.api.ops import Input, OpsIdentity
from app.modules.payments import service
from app.modules.payments.gateway import (
    Event,
    GatewayDisabled,
    InvalidSignature,
    get_gateway,
)

router = APIRouter()


class Create(Input):
    booking_id: UUID
    idempotency_key: UUID


def authorized(request: Request, identity=Depends(current_identity)):
    enforce_limit(request, "payment", str(identity["id"]))
    return identity


def webhook_limit(request: Request):
    enforce_limit(request, "payment_webhook")


async def invoke(operation, *args):
    try:
        return await operation(*args)
    except GatewayDisabled:
        raise HTTPException(503, "Payment gateway disabled") from None
    except LookupError:
        raise HTTPException(404, "Payment or booking not found") from None
    except ValueError:
        raise HTTPException(
            409, "Payment request conflicts with current state"
        ) from None


@router.post("/payments", status_code=202)
async def create(
    body: Create,
    request: Request,
    identity=Depends(authorized),
    gateway=Depends(get_gateway),
):
    return await invoke(
        service.initiate,
        request.app.state.engine,
        identity["id"],
        body.booking_id,
        body.idempotency_key,
        gateway,
    )


@router.get("/payments/{identifier}")
def get(identifier: UUID, request: Request, identity=Depends(current_identity)):
    try:
        return service.get(request.app.state.engine, identifier, identity)
    except LookupError:
        raise HTTPException(404, "Payment not found") from None


@router.post("/payments/webhook", dependencies=[Depends(webhook_limit)])
async def webhook(request: Request, gateway=Depends(get_gateway)):
    try:
        gateway.require_enabled()
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                raise HTTPException(413, "Webhook too large")
        # Adapter must authenticate exact bytes before returning any parsed event.
        result = await asyncio.wait_for(
            gateway.verify_webhook(bytes(body), dict(request.headers)),
            service.TIMEOUT_SECONDS,
        )
        event = Event.model_validate(
            result.model_dump() if isinstance(result, Event) else result
        )
    except GatewayDisabled:
        raise HTTPException(503, "Payment gateway disabled") from None
    except InvalidSignature:
        raise HTTPException(401, "Invalid webhook signature") from None
    except ValueError:
        raise HTTPException(400, "Invalid webhook event") from None
    except TimeoutError:
        raise HTTPException(503, "Webhook verification unavailable") from None
    try:
        await run_in_threadpool(service.apply, request.app.state.engine, event)
    except (LookupError, ValueError):
        raise HTTPException(409, "Webhook does not match payment") from None
    return {"status": "accepted"}


@router.post("/ops/payments/{identifier}/reconcile")
async def reconcile(
    identifier: UUID,
    body: Input,
    request: Request,
    actor: OpsIdentity,
    gateway=Depends(get_gateway),
):
    return await invoke(
        service.reconcile_one, request.app.state.engine, identifier, gateway
    )
