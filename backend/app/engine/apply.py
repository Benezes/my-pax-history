from __future__ import annotations

import uuid
from typing import Any

from app.constants import (
    DIFFICULTY_PARAMS,
    HIGHER_IS_WORSE,
    INDICATOR_BOUNDS,
    INDICATOR_LABELS,
    INCOME_BRACKETS,
    MAX_ABS_DELTA,
    REGIONS,
    Difficulty,
)
from app.models import GameState, HistoryEntry, ScheduledEffect


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def params(difficulty: Difficulty) -> dict[str, float]:
    return DIFFICULTY_PARAMS[difficulty]


def cap_delta(indicator: str, delta: float, intensity: float) -> float:
    limit = MAX_ABS_DELTA.get(indicator, 3.0) * intensity
    return clamp(delta, -limit, limit)


def set_value(state: GameState, key: str, value: float) -> None:
    if key == "coalition_support":
        bounds = INDICATOR_BOUNDS["coalition_support"]
        previous = state.congress.coalition_support
        state.congress.coalition_support = clamp(value, *bounds)
        state.indicators["coalition_support"] = state.congress.coalition_support
        from app.engine.congress import nudge_houses_by_support_delta

        nudge_houses_by_support_delta(state, previous)
        return
    if key in state.branches:
        bounds = INDICATOR_BOUNDS.get(key, (0.0, 100.0))
        state.branches[key] = clamp(value, *bounds)
        return
    bounds = INDICATOR_BOUNDS.get(key)
    if bounds is None:
        return
    state.indicators[key] = clamp(value, *bounds)


def get_value(state: GameState, key: str) -> float:
    if key == "coalition_support":
        return state.congress.coalition_support
    if key in state.branches:
        return state.branches[key]
    return float(state.indicators.get(key, 0.0))


def apply_delta(state: GameState, key: str, delta: float, intensity: float) -> float:
    applied = cap_delta(key, delta, intensity)
    set_value(state, key, get_value(state, key) + applied)
    return applied


def apply_many(state: GameState, deltas: dict[str, float], intensity: float) -> dict[str, float]:
    applied: dict[str, float] = {}
    for key, delta in deltas.items():
        applied[key] = apply_delta(state, key, delta, intensity)
    return applied


def push_history(
    state: GameState,
    kind: str,
    title: str,
    body: str,
    countries: list[str] | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    state.history.append(
        HistoryEntry(
            id=new_id(),
            month_index=state.date.month_index(),
            date_label=state.date.label(),
            kind=kind,  # type: ignore[arg-type]
            title=title,
            body=body,
            countries=countries or [],
            meta=meta or {},
        )
    )
    overflow = len(state.history) - 120
    if overflow > 0:
        dropped = state.history[:overflow]
        state.history = state.history[overflow:]
        digest = "; ".join(f"{e.date_label}: {e.title}" for e in dropped[-8:])
        state.memory_summary = (state.memory_summary + " " + digest).strip()[-4000:]


def format_delta(key: str, delta: float) -> str:
    from app.formatters import br_num

    label = INDICATOR_LABELS.get(key, key)
    if key in {"selic", "inflation", "unemployment", "gdp_growth", "poverty", "fiscal_primary_result"}:
        return f"{label} {br_num(delta, 2, signed=True)} p.p."
    if key in {"public_debt_gdp"}:
        return f"{label} {br_num(delta, 2, signed=True)} p.p. do PIB"
    if key == "exchange_rate_usd":
        return f"{label} {br_num(delta, 2, signed=True)}"
    return f"{label} {br_num(delta, 1, signed=True)}"


def sync_derived(state: GameState) -> None:
    state.indicators["coalition_support"] = state.congress.coalition_support
    approval = state.indicators["approval"]
    for region in REGIONS:
        current = state.approval_breakdown.regions.get(region, approval)
        state.approval_breakdown.regions[region] = clamp(current + (approval - current) * 0.15, 0, 100)
    for bracket in INCOME_BRACKETS:
        current = state.approval_breakdown.income.get(bracket, approval)
        state.approval_breakdown.income[bracket] = clamp(current + (approval - current) * 0.12, 0, 100)
    for party in state.congress.parties:
        if party.bloc == "government":
            party.stance = clamp(party.stance + (state.congress.coalition_support - 50) * 0.02, -100, 100)


def regenerate_resources(state: GameState) -> None:
    p = params(state.difficulty)
    approval = state.indicators["approval"]
    coalition = state.congress.coalition_support
    regen = (3.1 + (approval - 45.0) * 0.045 + (coalition - 40.0) * 0.05) * p["capital_regen"]
    regen = clamp(regen, 0.35, 8.5)
    set_value(state, "political_capital", get_value(state, "political_capital") + regen)
    inflow = state.budget.monthly_replenish_brl_bi
    primary = state.indicators.get("fiscal_primary_result", 0.0)
    inflow += primary * 0.35
    if state.indicators["gdp_growth"] < 0:
        inflow *= 0.85
    state.budget.fiscal_space_brl_bi = clamp(
        state.budget.fiscal_space_brl_bi + inflow,
        0.0,
        state.budget.fiscal_space_annual_cap_brl_bi,
    )
    if state.date.month == 1 and state.months_elapsed > 0:
        leftover = state.budget.fiscal_space_brl_bi * 0.3
        state.budget.fiscal_space_brl_bi = clamp(
            leftover + state.budget.fiscal_space_annual_cap_brl_bi * 0.7,
            0.0,
            state.budget.fiscal_space_annual_cap_brl_bi,
        )
        state.budget.year_spent_brl_bi = 0.0


def apply_macro(state: GameState, rng) -> dict[str, float]:
    intensity = params(state.difficulty)["consequence_intensity"]
    selic = state.indicators["selic"]
    inflation = state.indicators["inflation"]
    real_rate = selic - inflation
    deltas: dict[str, float] = {}
    if real_rate > 6.5:
        deltas["inflation"] = -0.09
        deltas["gdp_growth"] = -0.05
        deltas["unemployment"] = 0.04
        deltas["exchange_rate_usd"] = -0.03
    elif real_rate < 2.0:
        deltas["inflation"] = 0.11
        deltas["gdp_growth"] = 0.04
        deltas["unemployment"] = -0.03
        deltas["exchange_rate_usd"] = 0.06
    else:
        deltas["inflation"] = (4.0 - inflation) * 0.04
        deltas["gdp_growth"] = (2.0 - state.indicators["gdp_growth"]) * 0.03
    debt_drift = (selic / 12.0) * 0.35 - state.indicators["gdp_growth"] / 12.0 * 0.4
    debt_drift -= state.indicators.get("fiscal_primary_result", 0.0) * 0.08
    deltas["public_debt_gdp"] = debt_drift
    if state.indicators["crime_index"] > 65:
        deltas["approval"] = deltas.get("approval", 0.0) - 0.25
    if inflation > 6:
        deltas["approval"] = deltas.get("approval", 0.0) - 0.35
    if state.indicators["unemployment"] > 9:
        deltas["poverty"] = 0.12
        deltas["approval"] = deltas.get("approval", 0.0) - 0.2
    media = state.indicators.get("media_climate", 50.0)
    if media < 42:
        deltas["approval"] = deltas.get("approval", 0.0) - 0.25
    elif media > 60:
        deltas["approval"] = deltas.get("approval", 0.0) + 0.12
    deltas["approval"] = deltas.get("approval", 0.0) + rng.uniform(-0.18, 0.18)
    noise_keys = list(deltas.keys())
    for key in noise_keys:
        deltas[key] += rng.uniform(-0.02, 0.02)
    return apply_many(state, deltas, intensity)


def fire_scheduled(state: GameState) -> list[ScheduledEffect]:
    due = [e for e in state.scheduled_effects if e.fire_month_index <= state.date.month_index()]
    state.scheduled_effects = [
        e for e in state.scheduled_effects if e.fire_month_index > state.date.month_index()
    ]
    intensity = params(state.difficulty)["consequence_intensity"]
    for effect in due:
        applied = apply_many(state, effect.deltas, intensity)
        parts = [format_delta(k, v) for k, v in applied.items() if abs(v) > 0.01]
        prefix = "Efeito inesperado: " if effect.unexpected else "Efeito defasado: "
        push_history(
            state,
            "indicator",
            prefix + effect.description,
            "; ".join(parts) if parts else effect.description,
            effect.countries,
        )
        if effect.countries:
            merge_highlights(state, effect.countries)
    return due


def merge_highlights(state: GameState, countries: list[str]) -> None:
    ordered: list[str] = []
    for iso in ["BRA", *countries, *state.highlighted_countries]:
        if iso and iso not in ordered:
            ordered.append(iso)
    state.highlighted_countries = ordered[:10]


def schedule(
    state: GameState,
    description: str,
    deltas: dict[str, float],
    delay_months: int,
    source: str,
    unexpected: bool = False,
    countries: list[str] | None = None,
) -> None:
    if delay_months <= 0 or not deltas:
        return
    state.scheduled_effects.append(
        ScheduledEffect(
            id=new_id(),
            fire_month_index=state.date.month_index() + delay_months,
            source=source,
            description=description,
            deltas=deltas,
            unexpected=unexpected,
            countries=countries or [],
        )
    )


def quality_label(key: str, delta: float) -> str:
    worse = (delta > 0 and key in HIGHER_IS_WORSE) or (delta < 0 and key not in HIGHER_IS_WORSE)
    return "risco" if worse else "ganho"
