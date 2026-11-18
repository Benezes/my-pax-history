from __future__ import annotations

from random import Random

from app.constants import DIFFICULTY_PARAMS
from app.formatters import br_num
from app.models import ActionProposal, GameState, Party


def party_yes_probability(party: Party, proposal: ActionProposal, state: GameState) -> float:
    base = 0.5 + party.stance / 200.0
    if party.bloc == "government":
        base += 0.22
    elif party.bloc == "allied":
        base += 0.08
    elif party.bloc == "opposition":
        base -= 0.18
    approval = state.indicators["approval"]
    base += (approval - 50.0) / 400.0
    if proposal.category in {"fiscal", "institutional"} and party.bloc == "opposition":
        base -= 0.08
    if proposal.category == "social" and party.bloc == "opposition":
        base -= 0.04
    discipline = party.discipline / 100.0
    aligned = 0.5 + party.stance / 200.0
    return max(0.04, min(0.96, base * (0.35 + 0.65 * discipline) + aligned * 0.1))


def projected_votes(state: GameState, proposal: ActionProposal) -> tuple[float, float]:
    chamber_yes = 0.0
    chamber_total = 0
    senate_yes = 0.0
    senate_total = 0
    for party in state.congress.parties:
        p = party_yes_probability(party, proposal, state)
        chamber_yes += party.chamber_seats * p
        chamber_total += party.chamber_seats
        senate_yes += party.senate_seats * p
        senate_total += party.senate_seats
    chamber_share = chamber_yes / max(1, chamber_total)
    senate_share = senate_yes / max(1, senate_total)
    return chamber_share, senate_share


def pass_chance(state: GameState, proposal: ActionProposal) -> float:
    if not proposal.requires_congress:
        return 1.0
    chamber, senate = projected_votes(state, proposal)
    coalition = state.congress.coalition_support / 100.0
    relation = state.branches.get("executive_legislative", 50) / 100.0
    difficulty = DIFFICULTY_PARAMS[state.difficulty]
    raw = (
        chamber * 0.45
        + senate * 0.25
        + coalition * 0.2
        + relation * 0.1
        - proposal.congress_difficulty / 280.0
        - difficulty["pass_threshold_penalty"] / 100.0
        - difficulty["opposition_block_bonus"] / 200.0
    )
    raw += {"medio": 0.18, "dificil": 0.07, "impossivel": 0.0}[state.difficulty]
    return max(0.05, min(0.92, raw))


def roll_vote(state: GameState, proposal: ActionProposal, rng: Random) -> tuple[bool, str, float]:
    chance = pass_chance(state, proposal)
    if not proposal.requires_congress:
        return True, "Medida de competência privativa do Executivo.", chance
    passed = rng.random() < chance
    chamber, senate = projected_votes(state, proposal)
    if passed:
        reason = (
            f"Aprovado no Congresso (probabilidade {br_num(chance * 100, 0)}%; "
            f"projeção Câmara {br_num(chamber * 100, 0)}%, Senado {br_num(senate * 100, 0)}%)."
        )
    else:
        reason = (
            f"Rejeitado no Congresso (probabilidade {br_num(chance * 100, 0)}%; "
            f"projeção Câmara {br_num(chamber * 100, 0)}%, Senado {br_num(senate * 100, 0)}%). "
            f"A oposição e o centrão exploraram a fragilidade da base."
        )
    return passed, reason, chance
