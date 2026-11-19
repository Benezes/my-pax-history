from __future__ import annotations

import math
from random import Random

from app.constants import (
    COALITION_CHAMBER_MAX,
    COALITION_CHAMBER_MIN,
    COALITION_SENATE_MAX,
    COALITION_SENATE_MIN,
    DIFFICULTY_PARAMS,
    HOUSE_PASS_STEEPNESS,
    INDEPENDENT_SWING,
    MAJORITY_THRESHOLD,
    ORDINARY_YES_RATES,
    PEC_MARKERS,
    PEC_THRESHOLD,
    PEC_YES_RATES,
)
from app.engine.mandate import MandateAssessment, mandate_pass_delta
from app.formatters import br_num
from app.models import ActionProposal, Chamber, GameState


def is_constitutional_amendment(proposal: ActionProposal | None, raw_text: str = "") -> bool:
    if proposal is not None and proposal.constitutional_amendment:
        return True
    parts = [raw_text or ""]
    if proposal is not None:
        parts.extend([proposal.title, proposal.summary, " ".join(proposal.tags)])
    blob = " ".join(parts).lower()
    padded = f" {blob} "
    return any(marker in padded or marker in blob for marker in PEC_MARKERS)


def stamp_amendment(proposal: ActionProposal, raw_text: str = "") -> ActionProposal:
    if is_constitutional_amendment(proposal, raw_text):
        proposal.constitutional_amendment = True
    return proposal


def vote_threshold(proposal: ActionProposal | None, raw_text: str = "") -> float:
    return PEC_THRESHOLD if is_constitutional_amendment(proposal, raw_text) else MAJORITY_THRESHOLD


def _house_share(chamber: Chamber, pec: bool, approval: float) -> float:
    rates = PEC_YES_RATES if pec else ORDINARY_YES_RATES
    total = max(1, chamber.seats)
    yes = (
        chamber.government * rates["government"]
        + chamber.allied * rates["allied"]
        + chamber.independent * rates["independent"]
        + chamber.opposition * rates["opposition"]
    )
    share = yes / total
    share += (approval - 50.0) / 400.0
    coalition = (chamber.government + chamber.allied) / total
    independent = chamber.independent / total
    floor = coalition * 0.84 if pec else coalition + independent * INDEPENDENT_SWING
    return max(0.05, min(0.95, max(share, floor)))


def projected_votes(state: GameState, proposal: ActionProposal) -> tuple[float, float]:
    pec = is_constitutional_amendment(proposal)
    approval = state.indicators.get("approval", 50.0)
    return (
        _house_share(state.congress.chamber, pec, approval),
        _house_share(state.congress.senate, pec, approval),
    )


def house_pass_probability(share: float, threshold: float) -> float:
    return 1.0 / (1.0 + math.exp(-HOUSE_PASS_STEEPNESS * (share - threshold)))


def pass_chance(
    state: GameState, proposal: ActionProposal, mandate: MandateAssessment | None = None
) -> float:
    if not proposal.requires_congress:
        return 1.0
    pec = is_constitutional_amendment(proposal)
    threshold = PEC_THRESHOLD if pec else MAJORITY_THRESHOLD
    chamber, senate = projected_votes(state, proposal)
    difficulty = DIFFICULTY_PARAMS[state.difficulty]
    relation = state.branches.get("executive_legislative", 50) / 100.0
    raw = (
        house_pass_probability(chamber, threshold) * 0.52
        + house_pass_probability(senate, threshold) * 0.38
        + relation * 0.10
        - difficulty["pass_threshold_penalty"] / 100.0
        - difficulty["opposition_block_bonus"] / 200.0
    )
    if not pec and chamber >= MAJORITY_THRESHOLD and senate >= MAJORITY_THRESHOLD:
        raw += 0.02
    if mandate is not None:
        raw += mandate_pass_delta(mandate)
    return max(0.05, min(0.95, raw))


def _rejection_flavor(
    proposal: ActionProposal,
    chamber: float,
    senate: float,
    threshold: float,
    pec: bool,
    state: GameState,
) -> str:
    coalition = state.congress.coalition_support / 100.0
    title = (proposal.title or "a medida").strip()
    short = title if len(title) < 56 else title[:53] + "…"
    if pec:
        missing: list[str] = []
        if chamber < threshold:
            missing.append(
                f"na Câmara ({br_num(chamber * 100, 0)}%, precisava de {br_num(threshold * 100, 0)}%)"
            )
        if senate < threshold:
            missing.append(
                f"no Senado ({br_num(senate * 100, 0)}%, precisava de {br_num(threshold * 100, 0)}%)"
            )
        where = " e ".join(missing) if missing else "nas duas Casas"
        return (
            f"«{short}» é PEC e exige três quintos (3/5) nas duas Casas. "
            f"Faltaram votos {where}."
        )
    if chamber < threshold and senate >= threshold:
        return (
            f"«{short}» caiu na Câmara ({br_num(chamber * 100, 0)}% a favor, "
            f"maioria simples exigida). O Senado projetava {br_num(senate * 100, 0)}%."
        )
    if senate < threshold and chamber >= threshold:
        return (
            f"«{short}» passou da Câmara na projeção, mas o Senado não fechou "
            f"({br_num(senate * 100, 0)}% a favor)."
        )
    if coalition >= 0.5:
        return (
            f"Mesmo com base majoritária, independentes e parte da base não fecharam com "
            f"«{short}» (Câmara {br_num(chamber * 100, 0)}%, Senado {br_num(senate * 100, 0)}%)."
        )
    return (
        f"A base minoritária não reuniu maioria simples para «{short}» "
        f"(Câmara {br_num(chamber * 100, 0)}%, Senado {br_num(senate * 100, 0)}%)."
    )


def roll_vote(
    state: GameState,
    proposal: ActionProposal,
    rng: Random,
    mandate: MandateAssessment | None = None,
) -> tuple[bool, str, float]:
    chance = pass_chance(state, proposal, mandate)
    if not proposal.requires_congress:
        return True, "Medida de competência privativa do Executivo.", chance
    passed = rng.random() < chance
    chamber, senate = projected_votes(state, proposal)
    pec = is_constitutional_amendment(proposal)
    threshold = PEC_THRESHOLD if pec else MAJORITY_THRESHOLD
    quorum = (
        "quórum de três quintos (3/5) nas duas Casas"
        if pec
        else "maioria simples nas duas Casas"
    )
    if passed:
        reason = (
            f"Aprovada no Congresso ({quorum}; probabilidade {br_num(chance * 100, 0)}%; "
            f"projeção Câmara {br_num(chamber * 100, 0)}%, Senado {br_num(senate * 100, 0)}%)."
        )
    else:
        reason = (
            f"Rejeitada no Congresso (probabilidade {br_num(chance * 100, 0)}%; "
            f"projeção Câmara {br_num(chamber * 100, 0)}%, Senado {br_num(senate * 100, 0)}%). "
            + _rejection_flavor(proposal, chamber, senate, threshold, pec, state)
        )
    return passed, reason, chance


def _coalition_seat_share(chamber: Chamber) -> float:
    return (chamber.government + chamber.allied) / max(1, chamber.seats)


def nudge_houses_by_support_delta(state: GameState, previous_support: float) -> None:
    """Move each house by the coalition-support change, keeping their own bases."""
    from app.engine.election import _shift_chamber, _sync_parties

    delta_share = (state.congress.coalition_support - previous_support) / 100.0
    if abs(delta_share) < 1e-12:
        return
    chamber = _shift_chamber(
        state.congress.chamber,
        _coalition_seat_share(state.congress.chamber) + delta_share,
        0.0,
        COALITION_CHAMBER_MIN,
        COALITION_CHAMBER_MAX,
    )
    senate = _shift_chamber(
        state.congress.senate,
        _coalition_seat_share(state.congress.senate) + delta_share,
        0.0,
        COALITION_SENATE_MIN,
        COALITION_SENATE_MAX,
    )
    state.congress.chamber = chamber
    state.congress.senate = senate
    state.congress.parties = _sync_parties(state.congress.parties, chamber, senate)


def sync_congress_to_support(state: GameState) -> None:
    """Compatibility wrapper: do not snap both houses to the same share."""
    nudge_houses_by_support_delta(state, state.congress.coalition_support)
