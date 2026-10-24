from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field, StringConstraints, model_validator

from app.api.ops import Input, OpsIdentity
from app.modules.ops import service

router = APIRouter(prefix="/ops")
PageSize = Annotated[int, Query(ge=1, le=100)]


class Create(Input):
    booking_id: UUID


class Action(Input):
    idempotency_key: UUID
    version: int = Field(strict=True, ge=1)
    action: Literal["assign", "record", "escalate", "resolve", "reopen"]
    assigned_to: UUID | None = None
    evidence_id: UUID | None = None
    note: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def prerequisites(self):
        if self.action == "assign":
            if (
                self.assigned_to is None
                or self.note is not None
                or self.evidence_id is not None
            ):
                raise ValueError("Assignment requires only an assignee")
        elif (
            self.assigned_to is not None
            or self.note is None
            or self.evidence_id is None
        ):
            raise ValueError("Action and evidence required")
        return self


def call(function, *args):
    try:
        return function(*args)
    except LookupError:
        raise HTTPException(404, "Case or booking not found") from None
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


@router.get("/queues/{kind}")
def queue(
    kind: Literal[
        "pending-confirmations",
        "failed-bookings",
        "payment-review",
        "failed-notifications",
        "escalations",
    ],
    request: Request,
    actor: OpsIdentity,
    limit: PageSize = 50,
    after: UUID | None = None,
):
    return service.queue(request.app.state.engine, kind, limit, after)


@router.post("/cases", status_code=201)
def create(body: Create, request: Request, actor: OpsIdentity):
    return call(service.create, request.app.state.engine, actor["id"], body.booking_id)


@router.get("/cases/{identifier}")
def get(identifier: UUID, request: Request, actor: OpsIdentity):
    return call(service.get, request.app.state.engine, identifier)


@router.get("/cases/{identifier}/actions")
def history(
    identifier: UUID,
    request: Request,
    actor: OpsIdentity,
    limit: PageSize = 50,
    after: UUID | None = None,
):
    return call(service.history, request.app.state.engine, identifier, limit, after)


@router.post("/cases/{identifier}/actions")
def act(identifier: UUID, body: Action, request: Request, actor: OpsIdentity):
    return call(service.act, request.app.state.engine, actor["id"], identifier, body)
