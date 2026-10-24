from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import AwareDatetime, Field, model_validator

from app.api.ops import Input, OpsIdentity
from app.modules.inventory import service

router = APIRouter(prefix="/ops/inventory")
Quantity = Annotated[int, Field(strict=True, gt=0, le=2_147_483_647)]


class SlotCreate(Input):
    service_id: UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    release_at: AwareDatetime
    capacity: Quantity


class AvailabilityUpdate(Input):
    state: Literal[
        "UNKNOWN", "AVAILABLE_UNVERIFIED", "AVAILABLE_VERIFIED", "UNAVAILABLE"
    ]
    verified_until: AwareDatetime | None = None

    @model_validator(mode="after")
    def verification_required(self):
        if (self.state == "AVAILABLE_VERIFIED") != (self.verified_until is not None):
            raise ValueError(
                "Supply a verification deadline only for verified availability"
            )
        return self


class HoldCreate(Input):
    quantity: Quantity
    expires_at: AwareDatetime
    idempotency_key: UUID


def run(request, operation, *args):
    try:
        return operation(request.app.state.engine, *args)
    except LookupError as error:
        raise HTTPException(404, str(error)) from None
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


@router.post("/slots", status_code=201)
def create_slot(body: SlotCreate, request: Request, actor: OpsIdentity):
    return run(request, service.create_slot, actor["id"], body.model_dump())


@router.get("/slots/{slot_id}")
def get_slot(slot_id: UUID, request: Request, actor: OpsIdentity):
    return run(request, service.get_slot, slot_id)


@router.patch("/slots/{slot_id}/availability")
def availability(
    slot_id: UUID, body: AvailabilityUpdate, request: Request, actor: OpsIdentity
):
    return run(
        request,
        service.set_availability,
        actor["id"],
        slot_id,
        body.state,
        body.verified_until,
    )


@router.post("/slots/{slot_id}/refresh")
def refresh(slot_id: UUID, body: Input, request: Request, actor: OpsIdentity):
    return run(request, service.refresh_slot, actor["id"], slot_id)


@router.post("/slots/{slot_id}/holds", status_code=201)
def create_hold(slot_id: UUID, body: HoldCreate, request: Request, actor: OpsIdentity):
    return run(request, service.create_hold, actor["id"], slot_id, body.model_dump())


@router.post("/holds/{hold_id}/release")
def release(hold_id: UUID, body: Input, request: Request, actor: OpsIdentity):
    return run(request, service.release_hold, actor["id"], hold_id)
