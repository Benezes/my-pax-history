from __future__ import annotations

from app.constants import (
    COUNTRY_COORDS,
    COUNTRY_NAMES_PT,
    DIFFICULTY_LABELS,
    INDICATOR_LABELS,
    PROVIDER_LABELS,
)
from app.formatters import round_floats
from app.models import GameState, MapCountry, WhatIfResult


def map_countries(state: GameState) -> list[MapCountry]:
    highlighted = set(state.highlighted_countries)
    countries: dict[str, MapCountry] = {
        "BRA": MapCountry(
            iso="BRA",
            name="Brasil",
            lat=COUNTRY_COORDS["BRA"][0],
            lng=COUNTRY_COORDS["BRA"][1],
            highlight=True,
            relation=100,
        )
    }
    for power in state.powers.values():
        countries[power.iso] = MapCountry(
            iso=power.iso,
            name=power.name,
            lat=power.lat,
            lng=power.lng,
            highlight=power.iso in highlighted,
            relation=power.relation_brazil,
        )
    for iso in highlighted:
        if iso in countries:
            continue
        lat, lng = COUNTRY_COORDS.get(iso, (0.0, 0.0))
        countries[iso] = MapCountry(
            iso=iso,
            name=COUNTRY_NAMES_PT.get(iso, iso),
            lat=lat,
            lng=lng,
            highlight=True,
            relation=state.diplomacy.get(iso),
        )
    return list(countries.values())


def public_state(state: GameState) -> dict:
    indicators = [
        {
            "id": key,
            "label": INDICATOR_LABELS.get(key, key),
            "value": value,
        }
        for key, value in state.indicators.items()
        if key in INDICATOR_LABELS
    ]
    payload = {
        "id": state.id,
        "name": state.name,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "difficulty": state.difficulty,
        "difficulty_label": DIFFICULTY_LABELS[state.difficulty],
        "provider": state.provider,
        "provider_label": PROVIDER_LABELS[state.provider],
        "provider_model": state.provider_model,
        "status": state.status,
        "date": state.date.model_dump(),
        "date_label": state.date.label(),
        "indicators": indicators,
        "indicator_map": state.indicators,
        "budget": state.budget.model_dump(),
        "political_capital": state.indicators.get("political_capital", 0),
        "congress": state.congress.model_dump(),
        "branches": state.branches,
        "agents": [agent.model_dump() for agent in state.agents.values()],
        "powers": [power.model_dump() for power in state.powers.values()],
        "orgs": [org.model_dump() for org in state.orgs.values()],
        "problems": [item.model_dump() for item in state.problems],
        "pending_actions": [item.model_dump() for item in state.pending_actions],
        "last_report": state.last_report.model_dump() if state.last_report else None,
        "last_llm_model": state.last_llm_model,
        "last_resolved": [item.model_dump() for item in state.last_resolved],
        "last_what_if": state.last_what_if.model_dump() if state.last_what_if else None,
        "advisor_log": [item.model_dump() for item in state.advisor_log[-40:]],
        "history": [item.model_dump() for item in state.history[-80:]],
        "highlighted_countries": state.highlighted_countries,
        "map_countries": [item.model_dump() for item in map_countries(state)],
        "scandals": state.scandals,
        "impeachment_pressure": state.impeachment_pressure,
        "coup_risk": state.coup_risk,
        "election_vote_share": state.election_vote_share,
        "loss_title": state.loss_title,
        "loss_body": state.loss_body,
        "months_elapsed": state.months_elapsed,
        "campaign_pending": state.campaign_pending and state.campaign is None,
        "campaign": state.campaign.model_dump() if state.campaign else None,
        "scheduled_count": len(state.scheduled_effects),
        "ministers": [item.model_dump() for item in state.ministers],
        "cabinet_mode": state.cabinet_mode,
        "approval_breakdown": state.approval_breakdown.model_dump(),
        "headlines": [item.model_dump() for item in state.headlines[-12:]],
        "memory_summary": state.memory_summary[-500:],
        "last_report_date_label": state.date.label() if state.last_report else None,
    }
    return round_floats(payload, 2)


def public_what_if(result: WhatIfResult) -> dict:
    return round_floats(result.model_dump(), 2)
