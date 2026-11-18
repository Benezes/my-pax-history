from __future__ import annotations

from app.constants import ELECTION_MONTH, ELECTION_YEAR, GameStatus, LOSS_REASONS
from app.engine.apply import params, push_history
from app.models import GameState


def apply_status(state: GameState, status: GameStatus) -> None:
    info = LOSS_REASONS[status]
    state.status = status
    state.loss_title = info["title"]
    state.loss_body = info["body"]
    if status == GameStatus.WON_ELECTION and state.election_vote_share is not None:
        state.loss_body = (
            f"{info['body']} Votação estimada pelo motor: {state.election_vote_share:.1f}%."
        )
    if status == GameStatus.LOST_ELECTION and state.election_vote_share is not None:
        state.loss_body = (
            f"{info['body']} Votação estimada pelo motor: {state.election_vote_share:.1f}%."
        )
    push_history(state, "loss", info["title"], state.loss_body, ["BRA"])


def election_share(state: GameState) -> float:
    approval = state.indicators["approval"]
    growth = state.indicators["gdp_growth"]
    inflation = state.indicators["inflation"]
    unemployment = state.indicators["unemployment"]
    crime = state.indicators["crime_index"]
    coalition = state.congress.coalition_support
    stability = state.indicators["institutional_stability"]
    share = (
        approval * 0.38
        + (50.0 + growth * 7.0) * 0.16
        + max(0.0, 55.0 - inflation * 4.0) * 0.12
        + max(0.0, 55.0 - unemployment * 3.2) * 0.12
        + (100.0 - crime) * 0.08
        + coalition * 0.08
        + stability * 0.06
    )
    penalty = {"medio": 0.0, "dificil": 2.5, "impossivel": 5.0}[state.difficulty]
    return max(18.0, min(78.0, share - penalty))


def evaluate_loss(state: GameState) -> None:
    if state.status != GameStatus.PLAYING:
        return
    p = params(state.difficulty)
    approval = state.indicators["approval"]
    coalition = state.congress.coalition_support
    armed = state.agents["forcas_armadas"].stance
    stability = state.indicators["institutional_stability"]

    crisis = approval < 22 and coalition < 35
    if crisis:
        state.consecutive_crisis_months += 1
    else:
        state.consecutive_crisis_months = 0

    if approval < 25:
        state.impeachment_pressure += 4.0 * p["consequence_intensity"]
    if coalition < 32:
        state.impeachment_pressure += 5.0
    if state.scandals >= 1:
        state.impeachment_pressure += state.scandals * 6.0
    if approval > 45 and coalition > 48:
        state.impeachment_pressure = max(0.0, state.impeachment_pressure - 6.0)

    if armed < -20 and approval < 28:
        state.coup_risk += 7.0 * p["agent_hostility"]
    if stability < 38:
        state.coup_risk += 5.0
    if armed > 10 and stability > 55:
        state.coup_risk = max(0.0, state.coup_risk - 4.0)

    impeached = (
        (state.impeachment_pressure >= 100 and coalition < 42)
        or (state.consecutive_crisis_months >= 3 and approval < 20)
        or (state.scandals >= 3 and coalition < 40 and approval < 35)
    )
    if impeached:
        apply_status(state, GameStatus.LOST_IMPEACHMENT)
        return

    couped = state.coup_risk >= 100 and armed < -25 and stability < 40
    if couped:
        apply_status(state, GameStatus.LOST_COUP)
        return

    if state.date.year == ELECTION_YEAR and state.date.month == ELECTION_MONTH:
        share = election_share(state)
        state.election_vote_share = share
        if share >= 50.0:
            apply_status(state, GameStatus.WON_ELECTION)
        else:
            apply_status(state, GameStatus.LOST_ELECTION)
