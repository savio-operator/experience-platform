import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from app.api.auth import current_identity, enforce_limit
from app.api.ops import OpsIdentity
from app.modules.planning import service

router = APIRouter()


@router.put("/ops/inventory/slots/{slot_id}/offer")
def save_offer(slot_id: UUID, body: dict, request: Request, actor: OpsIdentity):
    try:
        offer = service.Offer.model_validate_json(json.dumps(body))
    except ValidationError:
        raise HTTPException(422, "Invalid offer") from None
    try:
        return service.save_offer(request.app.state.engine, actor["id"], slot_id, offer)
    except LookupError:
        raise HTTPException(404, "Slot not found") from None
    except ValueError:
        raise HTTPException(409, "Invalid verification window") from None


def authorized(request: Request, identity=Depends(current_identity)):
    enforce_limit(request, "options", str(identity["id"]))
    return identity


@router.post("/options")
def options(body: service.Search, request: Request, identity=Depends(authorized)):
    return service.generate(request.app.state.engine, body)
