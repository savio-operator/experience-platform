from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints, model_validator

from app.api.auth import require_role
from app.modules.catalogue import service as catalogue
from app.modules.vendors import service as vendors

router = APIRouter(prefix="/ops")
OpsIdentity = Annotated[dict, Depends(require_role("ops_admin"))]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VendorCreate(Input):
    name: Name
    contact_name: Name | None = None
    contact_email: EmailStr | None = None
    contact_phone: Phone | None = None
    terms_notes: Notes | None = None


class UpdateInput(Input):
    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set or (
            "name" in self.model_fields_set and self.name is None
        ):
            raise ValueError("Provide changes and a non-null name if included")
        return self


class VendorUpdate(UpdateInput):
    name: Name | None = None
    contact_name: Name | None = None
    contact_email: EmailStr | None = None
    contact_phone: Phone | None = None
    terms_notes: Notes | None = None


class ServiceCreate(Input):
    vendor_id: UUID
    name: Name
    description: Notes | None = None


class ServiceUpdate(UpdateInput):
    name: Name | None = None
    description: Notes | None = None


@router.post("/vendors", status_code=201)
def create_vendor(body: VendorCreate, request: Request, actor: OpsIdentity):
    return vendors.create_vendor(
        request.app.state.engine, actor["id"], body.model_dump(exclude_unset=True)
    )


@router.patch("/vendors/{vendor_id}")
def update_vendor(
    vendor_id: UUID, body: VendorUpdate, request: Request, actor: OpsIdentity
):
    try:
        return vendors.update_vendor(
            request.app.state.engine,
            actor["id"],
            vendor_id,
            body.model_dump(exclude_unset=True),
        )
    except LookupError as error:
        raise HTTPException(404, str(error)) from None


@router.post("/services", status_code=201)
def create_service(body: ServiceCreate, request: Request, actor: OpsIdentity):
    try:
        return catalogue.create_service(
            request.app.state.engine, actor["id"], body.model_dump(exclude_unset=True)
        )
    except LookupError as error:
        raise HTTPException(404, str(error)) from None


@router.patch("/services/{service_id}")
def update_service(
    service_id: UUID, body: ServiceUpdate, request: Request, actor: OpsIdentity
):
    try:
        return catalogue.update_service(
            request.app.state.engine,
            actor["id"],
            service_id,
            body.model_dump(exclude_unset=True),
        )
    except LookupError as error:
        raise HTTPException(404, str(error)) from None
