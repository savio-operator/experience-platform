from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import AwareDatetime

from app.api.auth import current_identity
from app.api.ops import Input, OpsIdentity
from app.modules.notifications import service
from app.modules.notifications.delivery import DeliveryDisabled, get_delivery

router = APIRouter()


class Reminder(Input):
    due_at: AwareDatetime


@router.post("/ops/bookings/{identifier}/reminders", status_code=201)
def schedule(identifier: UUID, body: Reminder, request: Request, actor: OpsIdentity):
    try:
        return service.schedule(
            request.app.state.engine, identifier, body.due_at, actor["id"]
        )
    except LookupError:
        raise HTTPException(404, "Booking not found") from None
    except ValueError:
        raise HTTPException(409, "Reminder not eligible") from None


@router.get("/notifications/{identifier}")
def get(identifier: UUID, request: Request, identity=Depends(current_identity)):
    try:
        return service.get(request.app.state.engine, identifier, identity)
    except LookupError:
        raise HTTPException(404, "Notification not found") from None


@router.post("/ops/notifications/{identifier}/dispatch")
def dispatch(
    identifier: UUID,
    body: Input,
    request: Request,
    actor: OpsIdentity,
    delivery=Depends(get_delivery),
):
    try:
        return service.dispatch(request.app.state.engine, delivery, identifier)
    except DeliveryDisabled:
        raise HTTPException(503, "Notification delivery disabled") from None
