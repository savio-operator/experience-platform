"""No live adapters or network calls are enabled in this step."""

from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field

Count = Annotated[int, Field(strict=True, ge=0, le=9_007_199_254_740_991)]


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    input_tokens: Count | None = None
    output_tokens: Count | None = None
    # INR paise, only when known from authoritative billing/rate information.
    cost_paise: Count | None = None


class ProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    output: str = Field(max_length=16_000)
    usage: Usage = Field(default_factory=Usage)


class Provider(Protocol):
    async def extract(
        self, *, instructions: str, user_text: str, schema: dict
    ) -> ProviderResult: ...


class ProviderDisabled(Exception):
    pass


class DisabledProvider:
    async def extract(self, **kwargs):
        raise ProviderDisabled


def get_provider() -> Provider:
    # Tests override this dependency. No environment flag can enable paid calls.
    return DisabledProvider()
