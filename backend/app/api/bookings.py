from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import AwareDatetime, Field, model_validator

from app.api.auth import current_identity, enforce_limit
from app.api.ops import Input, OpsIdentity
from app.modules.bookings import service
from app.modules.planning.service import Kind
from app.modules.pricing.service import Money, Requirement

router = APIRouter()


class Create(Input):
    slot_id: UUID
    idempotency_key: UUID
    kind: Kind
    quantity: Annotated[int, Field(strict=True, gt=0, le=10_000)]
    budget_paise: Money
    expected_total_paise: Money
    expires_at: AwareDatetime
    requirements: list[Requirement] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_requirements(self):
        if len(self.requirements) != len({r.key for r in self.requirements}):
            raise ValueError("Duplicate requirements")
        return self


class Confirmation(Input):
    vendor_confirmation_id: UUID


def authorized(request: Request, identity=Depends(current_identity)):
    enforce_limit(request, "booking", str(identity["id"]))
    return identity


def run(request, operation, *args):
    try:
        return operation(request.app.state.engine, *args)
    except LookupError:
        raise HTTPException(404, "Booking or slot not found") from None
    except ValueError:
        raise HTTPException(
            409, "Booking request conflicts with current state"
        ) from None
    except PermissionError:
        raise HTTPException(403, "Permission denied") from None


@router.post("/bookings", status_code=201)
def create(body: Create, request: Request, identity=Depends(authorized)):
    return run(request, service.create, identity["id"], body)


@router.get("/bookings/{identifier}")
def get(identifier: UUID, request: Request, identity=Depends(current_identity)):
    return run(request, service.get, identifier, identity)


@router.post("/ops/bookings/{identifier}/confirm")
def confirm(identifier: UUID, body: Confirmation, request: Request, actor: OpsIdentity):
    return run(
        request,
        service.change,
        identifier,
        actor,
        "CONFIRMED",
        body.vendor_confirmation_id,
    )


@router.post("/ops/bookings/{identifier}/reject")
def reject(identifier: UUID, body: Input, request: Request, actor: OpsIdentity):
    return run(request, service.change, identifier, actor, "FAILED")
