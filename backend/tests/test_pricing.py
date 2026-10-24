from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.pricing.service import MAX_PAISE, Evaluation, evaluate

NOW = datetime(2030, 1, 1, tzinfo=UTC)


@pytest.fixture
def inputs():
    return dict(
        requirements=[
            dict(key="no_alcohol", strength="hard", operator="eq", expected=True)
        ],
        facts=[
            dict(
                key="no_alcohol",
                value=True,
                source_id=uuid4(),
                verified_until=NOW + timedelta(minutes=1),
            )
        ],
        components=[
            dict(
                service_id=uuid4(), quantity=2, unit_price_paise=100, unit_cost_paise=60
            )
        ],
        fees=[dict(key="synthetic_fee", amount_paise=20, cost_paise=5)],
        taxes=[dict(key="synthetic_tax", amount_paise=10)],
        budget_paise=230,
        minimum_margin_paise=95,
    )


def run(inputs):
    return evaluate(Evaluation.model_validate(inputs), now=NOW)


def test_explicit_price_breakdown(inputs):
    result = run(inputs)
    assert result["accepted"]
    assert (
        result["component_subtotal_paise"],
        result["fee_total_paise"],
        result["tax_total_paise"],
    ) == (200, 20, 10)
    assert (
        result["customer_total_paise"],
        result["component_cost_paise"],
        result["fee_cost_paise"],
        result["margin_paise"],
    ) == (230, 120, 5, 95)


@pytest.mark.parametrize(
    "change", ["missing", "stale", "expired", "false", "wrong_type"]
)
def test_hard_requirements_fail_closed(inputs, change):
    if change == "missing":
        inputs["facts"] = []
    elif change == "stale":
        inputs["facts"][0]["verified_until"] = NOW
    elif change == "expired":
        inputs["facts"][0]["verified_until"] = NOW - timedelta(seconds=1)
    elif change == "false":
        inputs["facts"][0]["value"] = False
    else:
        inputs["facts"][0]["value"] = 1
    result = run(inputs)
    assert not result["accepted"] and not result["hard_constraints_pass"]
    assert result["budget_pass"] and result["margin_pass"]


def test_soft_preference_not_mandatory(inputs):
    inputs["requirements"][0]["strength"] = "soft"
    inputs["facts"] = []
    result = run(inputs)
    assert result["accepted"]
    assert result["constraint_results"][0]["status"] == "unverified"


@pytest.mark.parametrize(
    "operator,actual,expected,accepted",
    [
        ("gte", 3, 3, True),
        ("gte", 2, 3, False),
        ("lte", 3, 3, True),
        ("lte", 4, 3, False),
        ("eq", "Kochi", "Kochi", True),
        ("eq", "Other", "Kochi", False),
    ],
)
def test_comparisons(inputs, operator, actual, expected, accepted):
    inputs["requirements"][0].update(operator=operator, expected=expected)
    inputs["facts"][0]["value"] = actual
    assert run(inputs)["accepted"] is accepted


def test_budget_and_margin_are_independent(inputs):
    inputs["budget_paise"] = 229
    result = run(inputs)
    assert (
        not result["accepted"] and not result["budget_pass"] and result["margin_pass"]
    )
    inputs["budget_paise"] = 230
    inputs["minimum_margin_paise"] = 96
    result = run(inputs)
    assert (
        not result["accepted"] and result["budget_pass"] and not result["margin_pass"]
    )


def test_loss_not_clamped(inputs):
    inputs["components"][0]["unit_cost_paise"] = 200
    inputs["minimum_margin_paise"] = 0
    assert run(inputs)["margin_paise"] == -185
    assert not run(inputs)["accepted"]


@pytest.mark.parametrize("amount", [-1, 1.5, "100", True, MAX_PAISE + 1, None])
def test_invalid_money(inputs, amount):
    inputs["components"][0]["unit_price_paise"] = amount
    with pytest.raises(ValidationError):
        run(inputs)


@pytest.mark.parametrize(
    "field",
    [
        "budget_paise",
        "minimum_margin_paise",
        "fees",
        "taxes",
        "requirements",
        "facts",
        "components",
    ],
)
def test_missing_input(inputs, field):
    del inputs[field]
    with pytest.raises(ValidationError):
        run(inputs)


@pytest.mark.parametrize(
    "field", ["requirements", "facts", "components", "fees", "taxes"]
)
def test_duplicate_inputs_rejected(inputs, field):
    inputs[field].append(inputs[field][0].copy())
    with pytest.raises(ValidationError):
        run(inputs)


def test_zero_and_max_boundaries(inputs):
    inputs.update(fees=[], taxes=[], budget_paise=0, minimum_margin_paise=0)
    inputs["components"][0].update(quantity=1, unit_price_paise=0, unit_cost_paise=0)
    assert run(inputs)["accepted"]
    inputs["components"][0]["unit_price_paise"] = MAX_PAISE
    inputs["budget_paise"] = MAX_PAISE
    assert run(inputs)["accepted"]
    inputs["fees"] = [dict(key="one", amount_paise=1, cost_paise=0)]
    with pytest.raises(ValueError):
        run(inputs)


def test_invalid_evidence_and_components(inputs):
    inputs["facts"][0]["verified_until"] = NOW.replace(tzinfo=None)
    with pytest.raises(ValidationError):
        run(inputs)
    inputs["facts"] = []
    inputs["components"][0]["quantity"] = 0
    with pytest.raises(ValidationError):
        run(inputs)
    inputs["components"][0]["quantity"] = 1
    del inputs["components"][0]["unit_cost_paise"]
    with pytest.raises(ValidationError):
        run(inputs)


def test_reject_unknown_fields_and_operators(inputs):
    inputs["requirements"][0]["operator"] = "execute"
    with pytest.raises(ValidationError):
        run(inputs)
    inputs["requirements"][0].update(operator="gte", expected=True)
    with pytest.raises(ValidationError):
        run(inputs)
    inputs["requirements"][0].update(operator="eq", bypass=True)
    with pytest.raises(ValidationError):
        run(inputs)


def test_no_naive_clock(inputs):
    with pytest.raises(ValueError):
        evaluate(Evaluation.model_validate(inputs), now=NOW.replace(tzinfo=None))


def test_soft_matches_cannot_outweigh_failed_hard_requirement(inputs):
    inputs["requirements"].append(
        dict(key="mandatory_unknown", strength="hard", operator="eq", expected=True)
    )
    inputs["requirements"][0]["strength"] = "soft"
    result = run(inputs)
    assert not result["accepted"]
    assert [c["status"] for c in result["constraint_results"]] == ["met", "unverified"]


@pytest.mark.parametrize("field", ["unit_price_paise", "unit_cost_paise"])
def test_quantity_multiplication_overflow(inputs, field):
    inputs["components"][0][field] = MAX_PAISE
    with pytest.raises(ValueError, match="supported integer range"):
        run(inputs)
