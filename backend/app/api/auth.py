from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.identity import service
from app.modules.identity.delivery import get_delivery

router = APIRouter(prefix="/auth")


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        # Account identifiers are case-insensitive; do not strip dots or plus tags.
        return value.casefold()


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: UUID
    code: str = Field(pattern=r"^[0-9]{6}$", strict=True)


def enforce_limit(request, operation, email=None):
    settings = request.app.state.settings
    retry = service.throttle(
        request.app.state.engine,
        settings.otp_hash_key,
        operation,
        request.client.host if request.client else "unknown",
        email,
    )
    if retry:
        raise HTTPException(
            429, "Too many attempts", headers={"Retry-After": str(retry)}
        )


def current_identity(request: Request):
    enforce_limit(request, "session")
    identity = service.get_identity(
        request.app.state.engine, request.cookies.get(service.COOKIE_NAME)
    )
    if identity is None:
        raise HTTPException(401, "Authentication required")
    return identity


def require_role(role):
    def check(identity=Depends(current_identity)):
        if role not in identity["roles"]:
            raise HTTPException(403, "Permission denied")
        return identity

    return check


def require_owner(identity, owner_user_id):
    if identity["id"] != owner_user_id:
        raise HTTPException(403, "Permission denied")


@router.post("/otp/request", status_code=202)
def request_code(body: EmailRequest, request: Request, delivery=Depends(get_delivery)):
    enforce_limit(request, "request", body.email)
    challenge_id = service.request_otp(
        request.app.state.engine,
        request.app.state.settings.otp_hash_key,
        body.email,
        delivery,
    )
    return {"status": "accepted", "challenge_id": challenge_id}


@router.post("/otp/verify", status_code=204)
def verify_code(body: VerifyRequest, request: Request):
    enforce_limit(request, "verify")
    token = service.verify_otp(
        request.app.state.engine,
        request.app.state.settings.otp_hash_key,
        body.challenge_id,
        body.code,
        request.cookies.get(service.COOKIE_NAME),
    )
    if token is None:
        raise HTTPException(400, "Invalid or expired code")
    response = Response(status_code=204)
    response.set_cookie(
        service.COOKIE_NAME,
        token,
        max_age=service.SESSION_SECONDS,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )
    return response


@router.get("/me")
def me(identity=Depends(current_identity)):
    return identity


@router.post("/logout", status_code=204)
def logout(request: Request):
    enforce_limit(request, "session")
    service.logout(request.app.state.engine, request.cookies.get(service.COOKIE_NAME))
    response = Response(status_code=204)
    response.delete_cookie(
        service.COOKIE_NAME, path="/", httponly=True, samesite="strict"
    )
    return response
