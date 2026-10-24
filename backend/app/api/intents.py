from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field

from app.ai.provider import ProviderDisabled, get_provider
from app.api.auth import current_identity, enforce_limit
from app.api.ops import Input
from app.modules.intents import service

router = APIRouter(prefix="/intents")


class IntentRequest(Input):
    text: Annotated[
        str, Field(strict=True, min_length=1, max_length=2000, pattern=r"\S")
    ]


def authorized(request: Request, identity=Depends(current_identity)):
    enforce_limit(request, "intent", str(identity["id"]))
    return identity


@router.post("/parse")
async def parse_intent(
    body: IntentRequest,
    request: Request,
    identity=Depends(authorized),
    provider=Depends(get_provider),
):
    try:
        return await service.extract(provider, body.text, request.state.request_id)
    except ProviderDisabled:
        raise HTTPException(503, "AI provider disabled") from None
    except service.InvalidProviderOutput:
        raise HTTPException(502, "Invalid provider response") from None
    except service.ProviderUnavailable:
        raise HTTPException(503, "AI provider unavailable") from None
