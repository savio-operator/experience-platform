"""Pure server-side evaluation; never accept client/model facts as evidence."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

MAX_PAISE = 9_007_199_254_740_991
Money = Annotated[int, Field(strict=True, ge=0, le=MAX_PAISE)]
Key = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=100)]
Value = Annotated[str, StringConstraints(strict=True, max_length=300)] | int | bool


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class Requirement(StrictModel):
    key: Key
    strength: Literal["hard", "soft"]
    operator: Literal["eq", "gte", "lte"]
    expected: Value

    @model_validator(mode="after")
    def comparable(self):
        if self.operator != "eq" and type(self.expected) is not int:
            raise ValueError("Ordered requirements require integers")
        return self


class Fact(StrictModel):
    key: Key
    value: Value
    source_id: UUID
    verified_until: AwareDatetime


class Component(StrictModel):
    service_id: UUID
    quantity: Annotated[int, Field(strict=True, gt=0, le=10_000)]
    unit_price_paise: Money
    unit_cost_paise: Money


class Fee(StrictModel):
    key: Key
    amount_paise: Money
    cost_paise: Money


class Tax(StrictModel):
    key: Key
    amount_paise: Money


class Evaluation(StrictModel):
    # All collections must be supplied, including explicit empty fees/taxes.
    requirements: list[Requirement] = Field(max_length=100)
    facts: list[Fact] = Field(max_length=100)
    components: list[Component] = Field(min_length=1, max_length=100)
    fees: list[Fee] = Field(max_length=100)
    taxes: list[Tax] = Field(max_length=100)
    budget_paise: Money
    minimum_margin_paise: Money

    @model_validator(mode="after")
    def unique_keys(self):
        for values, field in (
            (self.requirements, "key"),
            (self.facts, "key"),
            (self.components, "service_id"),
            (self.fees, "key"),
            (self.taxes, "key"),
        ):
            keys = [getattr(value, field) for value in values]
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate evaluation inputs")
        return self


def evaluate(values: Evaluation, *, now: datetime) -> dict:
    """Caller supplies authoritative facts/prices and a server UTC clock.

    Free-text intent constraints must be resolved into requirements first; unknown
    mandatory facts remain missing. This function performs no natural-language
    interpretation, price discovery, tax inference or booking operations.
    """
    values = Evaluation.model_validate(values.model_dump())
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Evaluation requires a timezone-aware server clock")
    facts = {fact.key: fact for fact in values.facts}
    checks = []
    for requirement in values.requirements:
        fact = facts.get(requirement.key)
        status = "unverified"
        if fact is not None and fact.verified_until > now:
            if type(fact.value) is not type(requirement.expected):
                status = "unverified"
            else:
                actual, expected = fact.value, requirement.expected
                matched = (
                    actual == expected
                    if requirement.operator == "eq"
                    else actual >= expected
                    if requirement.operator == "gte"
                    else actual <= expected
                )
                status = "met" if matched else "unmet"
        checks.append(
            {"key": requirement.key, "strength": requirement.strength, "status": status}
        )
    subtotal = sum(c.unit_price_paise * c.quantity for c in values.components)
    component_cost = sum(c.unit_cost_paise * c.quantity for c in values.components)
    fees = sum(f.amount_paise for f in values.fees)
    fee_cost = sum(f.cost_paise for f in values.fees)
    taxes = sum(t.amount_paise for t in values.taxes)
    total = subtotal + fees + taxes
    cost = component_cost + fee_cost
    # Taxes supplied here are pass-through collected amounts, not revenue.
    margin = subtotal + fees - cost
    if any(
        n > MAX_PAISE
        for n in (
            subtotal,
            component_cost,
            fees,
            fee_cost,
            taxes,
            total,
            cost,
            abs(margin),
        )
    ):
        raise ValueError("Pricing total exceeds supported integer range")
    hard_ok = all(c["status"] == "met" for c in checks if c["strength"] == "hard")
    budget_ok = total <= values.budget_paise
    margin_ok = margin >= values.minimum_margin_paise
    return {
        "accepted": hard_ok and budget_ok and margin_ok,
        "hard_constraints_pass": hard_ok,
        "constraint_results": checks,
        "component_subtotal_paise": subtotal,
        "fee_total_paise": fees,
        "tax_total_paise": taxes,
        "customer_total_paise": total,
        "budget_pass": budget_ok,
        "component_cost_paise": component_cost,
        "fee_cost_paise": fee_cost,
        "margin_paise": margin,
        "margin_pass": margin_ok,
    }
