import json
from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.modules.audit import service as audit
from app.modules.catalogue.models import services
from app.modules.inventory import service as inventory
from app.modules.inventory.models import inventory_slots as slots
from app.modules.planning.models import slot_offers
from app.modules.pricing import service as pricing

Kind = Literal["now_or_tonight", "date", "birthday_or_surprise"]


class Offer(pricing.StrictModel):
    source_id: UUID
    verified_until: AwareDatetime
    location: Literal["Kochi"]
    intents: list[Kind] = Field(min_length=1, max_length=3)
    unit_price_paise: pricing.Money
    unit_cost_paise: pricing.Money
    fees: list[pricing.Fee] = Field(max_length=100)
    taxes: list[pricing.Tax] = Field(max_length=100)
    minimum_margin_paise: pricing.Money
    facts: list[pricing.Fact] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_entries(self):
        if len(self.intents) != len(set(self.intents)):
            raise ValueError("Duplicate intents")
        for entries in (self.fees, self.taxes, self.facts):
            if len(entries) != len({entry.key for entry in entries}):
                raise ValueError("Duplicate offer entries")
        return self


class Search(pricing.StrictModel):
    kind: Kind
    starts_after: Annotated[AwareDatetime, Field(strict=False)]
    ends_before: Annotated[AwareDatetime, Field(strict=False)]
    quantity: Annotated[int, Field(strict=True, gt=0, le=10_000)]
    budget_paise: pricing.Money
    requirements: list[pricing.Requirement] = Field(max_length=100)

    @model_validator(mode="after")
    def valid_window(self):
        if not timedelta(0) < self.ends_before - self.starts_after <= timedelta(days=7):
            raise ValueError("Search window must be positive and at most seven days")
        if len(self.requirements) != len({r.key for r in self.requirements}):
            raise ValueError("Duplicate requirements")
        return self


def save_offer(engine, actor_id, slot_id, offer):
    with engine.begin() as conn:
        slot = inventory.lock_slot(conn, slot_id)
        now = conn.scalar(select(func.clock_timestamp()))
        if not now < offer.verified_until <= slot["release_at"]:
            raise ValueError("Offer verification must end within the release window")
        if any(not now < f.verified_until <= offer.verified_until for f in offer.facts):
            raise ValueError("Fact verification must end within the offer window")
        payload = offer.model_dump(mode="json")
        conn.execute(
            insert(slot_offers)
            .values(
                slot_id=slot_id,
                payload=payload,
                updated_by=actor_id,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[slot_offers.c.slot_id],
                set_={
                    "payload": payload,
                    "updated_by": actor_id,
                    "updated_at": now,
                },
            )
        )
        audit.record(conn, actor_id, "inventory_slot", slot_id, "updated", ["offer"])
    return {"slot_id": slot_id}


def evaluate_offer(conn, row, search, now):
    payload = conn.scalar(
        select(slot_offers.c.payload).where(slot_offers.c.slot_id == row["id"])
    )
    offer = Offer.model_validate_json(json.dumps(payload))
    if offer.verified_until <= now or search.kind not in offer.intents:
        raise ValueError("Offer is not current or suitable")
    result = pricing.evaluate(
        pricing.Evaluation(
            requirements=search.requirements,
            facts=offer.facts,
            components=[
                pricing.Component(
                    service_id=row["service_id"],
                    quantity=search.quantity,
                    unit_price_paise=offer.unit_price_paise,
                    unit_cost_paise=offer.unit_cost_paise,
                )
            ],
            fees=offer.fees,
            taxes=offer.taxes,
            budget_paise=search.budget_paise,
            minimum_margin_paise=offer.minimum_margin_paise,
        ),
        now=now,
    )
    return offer, result


def generate(engine, search):
    candidates = []
    with engine.begin() as conn:
        # Locks share the inventory mutation order. Results are observations,
        # never reservations; booking must recheck after these locks are released.
        rows = (
            conn.execute(
                select(slots, services.c.name.label("service_name"))
                .join(services, services.c.id == slots.c.service_id)
                .where(
                    slots.c.starts_at >= search.starts_after,
                    slots.c.ends_at <= search.ends_before,
                    slots.c.state.in_(["AVAILABLE_VERIFIED", "HELD"]),
                )
                .order_by(slots.c.id)
                .with_for_update(of=slots)
            )
            .mappings()
            .all()
        )
        for row in rows:
            now = conn.scalar(select(func.clock_timestamp()))
            slot = dict(row)
            current = inventory.snapshot(
                slot, now, inventory.active_quantity(conn, row["id"], now)
            )
            if current["available_quantity"] < search.quantity:
                continue
            try:
                offer, result = evaluate_offer(conn, row, search, now)
            except ValueError:
                # Corrupt or outdated server records cannot become options.
                continue
            if not result["accepted"]:
                continue
            valid_until = min(
                row["release_at"],
                row["verified_until"],
                offer.verified_until,
                *(
                    f.verified_until
                    for f in offer.facts
                    if f.verified_until > now
                    and f.key in {r.key for r in search.requirements}
                ),
            )
            candidates.append(
                {
                    "slot_id": row["id"],
                    "service_id": row["service_id"],
                    "service_name": row["service_name"],
                    "starts_at": row["starts_at"],
                    "ends_at": row["ends_at"],
                    "quantity": search.quantity,
                    "availability": "AVAILABLE_VERIFIED",
                    "observed_at": now,
                    "valid_until": valid_until,
                    "is_booking": False,
                    "component_subtotal_paise": result["component_subtotal_paise"],
                    "fee_total_paise": result["fee_total_paise"],
                    "tax_total_paise": result["tax_total_paise"],
                    "customer_total_paise": result["customer_total_paise"],
                    "constraint_results": result["constraint_results"],
                }
            )
        final_now = conn.scalar(select(func.clock_timestamp()))
        candidates = [c for c in candidates if c["valid_until"] > final_now]
    candidates.sort(
        key=lambda c: (
            -sum(
                r["strength"] == "soft" and r["status"] == "met"
                for r in c["constraint_results"]
            ),
            c["customer_total_paise"],
            c["starts_at"],
            str(c["slot_id"]),
        )
    )
    distinct = {}
    for candidate in candidates:
        distinct.setdefault(candidate["service_id"], candidate)
    return {"options": list(distinct.values())[:3]}
