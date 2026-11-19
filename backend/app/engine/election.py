from __future__ import annotations

import math
from random import Random

from app.constants import (
    CAMPAIGN_MAX_PROPOSALS,
    CAMPAIGN_MIN_PROPOSALS,
    CAMPAIGN_PROPOSAL_MAX_CHARS,
    CAMPAIGN_PROPOSAL_MIN_CHARS,
    COALITION_CHAMBER_MAX,
    COALITION_CHAMBER_MIN,
    COALITION_SENATE_MAX,
    COALITION_SENATE_MIN,
    ELECTION_DIFFICULTY_PENALTY_PP,
    ELECTION_FIRST_MAX,
    ELECTION_FIRST_MIN,
    ELECTION_FIRST_ROUND_BASE,
    ELECTION_PLATFORM_FIRST_PP,
    ELECTION_PLATFORM_RUNOFF_PP,
    ELECTION_RUNOFF_MAX,
    ELECTION_RUNOFF_MIN,
    HONEYMOON_APPROVAL_PER_MARGIN_PP,
    HONEYMOON_CAPITAL_BONUS,
    SEATS_PER_MARGIN_PP_CHAMBER,
    SEATS_PER_MARGIN_PP_SENATE,
    SEATS_PER_PLATFORM_CHAMBER,
    SEATS_PER_PLATFORM_SENATE,
)
from app.engine.apply import push_history
from app.formatters import br_num
from app.models import (
    CampaignClassification,
    CampaignMandateItem,
    CampaignProposalHint,
    CampaignResult,
    Chamber,
    Congress,
    GameState,
    Party,
)


def validate_proposals(raw: list[str]) -> list[str]:
    cleaned = [item.strip() for item in raw if item and item.strip()]
    if len(cleaned) < CAMPAIGN_MIN_PROPOSALS or len(cleaned) > CAMPAIGN_MAX_PROPOSALS:
        raise ValueError(
            f"A campanha precisa de {CAMPAIGN_MIN_PROPOSALS} a {CAMPAIGN_MAX_PROPOSALS} propostas principais."
        )
    unique: list[str] = []
    seen: set[str] = set()
    for item in cleaned:
        if len(item) < CAMPAIGN_PROPOSAL_MIN_CHARS:
            raise ValueError("Cada proposta precisa ter pelo menos 12 caracteres para o eleitor entender.")
        if len(item) > CAMPAIGN_PROPOSAL_MAX_CHARS:
            raise ValueError("Cada proposta pode ter no máximo 400 caracteres.")
        key = item.lower()
        if key in seen:
            raise ValueError("As propostas da campanha não podem ser repetidas.")
        seen.add(key)
        unique.append(item)
    return unique


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _allocate(total: int, weights: list[float]) -> list[int]:
    if not weights:
        return []
    positive = [max(0.0, w) for w in weights]
    if sum(positive) <= 0:
        positive = [1.0] * len(weights)
    raw = [total * w / sum(positive) for w in positive]
    floors = [int(item) for item in raw]
    leftover = total - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (raw[i] - floors[i], -i), reverse=True)
    for index in order[: max(0, leftover)]:
        floors[index] += 1
    return floors


def _pad_hints(texts: list[str], classification: CampaignClassification) -> list[CampaignProposalHint]:
    hints = list(classification.proposals)
    while len(hints) < len(texts):
        hints.append(CampaignProposalHint())
    return hints[: len(texts)]


def platform_strength(texts: list[str], classification: CampaignClassification) -> tuple[float, list[CampaignMandateItem]]:
    hints = _pad_hints(texts, classification)
    raw_weights: list[float] = []
    items: list[CampaignMandateItem] = []
    for index, text in enumerate(texts):
        hint = hints[index]
        popularity = _clamp(float(hint.popularity), 0.15, 0.95)
        alignment = _clamp(float(hint.alignment), 0.15, 0.95)
        raw = popularity * (0.45 + 0.55 * alignment)
        raw_weights.append(raw)
        keywords = [str(item).strip()[:40] for item in hint.keywords if str(item).strip()][:8]
        items.append(
            CampaignMandateItem(
                id=f"mandate-{index + 1}",
                text=text,
                category=hint.category,
                weight=0.0,
                popularity=popularity,
                alignment=alignment,
                keywords=keywords,
                summary=(hint.summary or text)[:280],
            )
        )
    total = sum(raw_weights) or 1.0
    for item, raw in zip(items, raw_weights):
        item.weight = round(raw / total, 4)
    coherence = _clamp(float(classification.platform_coherence), 0.2, 0.95)
    strength = _clamp(sum(raw_weights) / max(1, len(raw_weights)) * 0.82 + coherence * 0.18, 0.2, 0.95)
    return strength, items


def simulate_election(
    texts: list[str],
    classification: CampaignClassification,
    seed: int,
    difficulty: str,
) -> CampaignResult:
    rng = Random(seed ^ 0xC0FFEE)
    strength, items = platform_strength(texts, classification)
    penalty = ELECTION_DIFFICULTY_PENALTY_PP.get(difficulty, 0.0)
    first = (
        ELECTION_FIRST_ROUND_BASE
        + strength * ELECTION_PLATFORM_FIRST_PP
        - penalty
        + rng.uniform(-1.8, 1.8)
    )
    first = round(_clamp(first, ELECTION_FIRST_MIN, ELECTION_FIRST_MAX), 1)
    others = round(100.0 - first, 1)
    runoff = first < 50.0
    if runoff:
        second = first + 3.0 + strength * ELECTION_PLATFORM_RUNOFF_PP + rng.uniform(-0.8, 1.1)
        winner = round(_clamp(second, ELECTION_RUNOFF_MIN, ELECTION_RUNOFF_MAX), 1)
    else:
        winner = first
    opponent = round(100.0 - winner, 1)
    margin = round(winner - opponent, 1)
    narrative = classification.narrative.strip() or (
        "A campanha traduziu as propostas em uma frente eleitoral pragmática. "
        "O eleitorado premiou a clareza da plataforma e cobrará a entrega a partir de janeiro."
    )
    return CampaignResult(
        first_round_share=first,
        runoff=runoff,
        second_round_share=winner if runoff else None,
        winner_share=winner,
        opponent_share=opponent,
        margin_pp=margin,
        turnout=round(77.5 + strength * 4.0 + rng.uniform(-0.6, 0.8), 1),
        narrative=narrative,
        proposals=items,
        platform_strength=round(strength, 3),
    )


def _shift_chamber(
    chamber: Chamber, target_share: float, gov_tilt: float, min_share: float, max_share: float
) -> Chamber:
    total = chamber.seats
    low = math.ceil(total * min_share)
    high = int(total * max_share)
    coalition = int(round(total * _clamp(target_share, 0.0, 1.0)))
    coalition = max(low, min(high, coalition))
    gov_ratio = chamber.government / max(1, chamber.government + chamber.allied)
    gov_ratio = _clamp(gov_ratio + gov_tilt, 0.52, 0.74)
    government = int(round(coalition * gov_ratio))
    allied = coalition - government
    rest = total - coalition
    opp_ratio = chamber.opposition / max(1, chamber.opposition + chamber.independent)
    opposition = int(round(rest * opp_ratio))
    independent = rest - opposition
    if government + allied + opposition + independent != total:
        independent = total - government - allied - opposition
    return Chamber(
        seats=total,
        government=max(0, government),
        allied=max(0, allied),
        opposition=max(0, opposition),
        independent=max(0, independent),
    )


def _sync_parties(parties: list[Party], chamber: Chamber, senate: Chamber) -> list[Party]:
    cloned = [party.model_copy(deep=True) for party in parties]
    bloc_chamber = {
        "government": chamber.government,
        "allied": chamber.allied,
        "opposition": chamber.opposition,
        "independent": chamber.independent,
    }
    bloc_senate = {
        "government": senate.government,
        "allied": senate.allied,
        "opposition": senate.opposition,
        "independent": senate.independent,
    }
    for bloc, target in bloc_chamber.items():
        members = [party for party in cloned if party.bloc == bloc]
        if not members:
            continue
        seats = _allocate(target, [max(1.0, float(party.chamber_seats)) for party in members])
        for party, seat in zip(members, seats):
            party.chamber_seats = seat
    for bloc, target in bloc_senate.items():
        members = [party for party in cloned if party.bloc == bloc]
        if not members:
            continue
        seats = _allocate(target, [max(1.0, float(party.senate_seats)) for party in members])
        for party, seat in zip(members, seats):
            party.senate_seats = seat
    return cloned


def compose_congress(baseline: Congress, margin_pp: float, strength: float) -> Congress:
    chamber_share = (
        (baseline.chamber.government + baseline.chamber.allied) / max(1, baseline.chamber.seats)
        + margin_pp * SEATS_PER_MARGIN_PP_CHAMBER / max(1, baseline.chamber.seats)
        + strength * SEATS_PER_PLATFORM_CHAMBER / max(1, baseline.chamber.seats)
    )
    senate_share = (
        (baseline.senate.government + baseline.senate.allied) / max(1, baseline.senate.seats)
        + margin_pp * SEATS_PER_MARGIN_PP_SENATE / max(1, baseline.senate.seats)
        + strength * SEATS_PER_PLATFORM_SENATE / max(1, baseline.senate.seats)
    )
    chamber_share = _clamp(chamber_share, COALITION_CHAMBER_MIN, COALITION_CHAMBER_MAX)
    senate_share = _clamp(senate_share, COALITION_SENATE_MIN, COALITION_SENATE_MAX)
    gov_tilt = 0.03 + strength * 0.05
    chamber = _shift_chamber(
        baseline.chamber, chamber_share, gov_tilt, COALITION_CHAMBER_MIN, COALITION_CHAMBER_MAX
    )
    senate = _shift_chamber(
        baseline.senate, senate_share, gov_tilt, COALITION_SENATE_MIN, COALITION_SENATE_MAX
    )
    parties = _sync_parties(baseline.parties, chamber, senate)
    coalition = (chamber.government + chamber.allied) / max(1, chamber.seats) * 100.0
    return Congress(
        coalition_support=round(coalition, 1),
        chamber=chamber,
        senate=senate,
        parties=parties,
        plebiscite_unlocked=baseline.plebiscite_unlocked,
    )


def inaugurate(state: GameState, result: CampaignResult) -> GameState:
    congress = compose_congress(state.congress, result.margin_pp, result.platform_strength)
    result.coalition_support = congress.coalition_support
    result.chamber = congress.chamber
    result.senate = congress.senate
    state.congress = congress
    state.indicators["coalition_support"] = congress.coalition_support
    state.campaign = result
    state.campaign_pending = False
    approval = state.indicators.get("approval", 50.0) + result.margin_pp * HONEYMOON_APPROVAL_PER_MARGIN_PP
    state.indicators["approval"] = _clamp(approval, 20.0, 78.0)
    capital = state.indicators.get("political_capital", 40.0) + HONEYMOON_CAPITAL_BONUS
    state.indicators["political_capital"] = _clamp(capital, 0.0, 100.0)
    relation = state.branches.get("executive_legislative", 44.0) + 4.0 + result.platform_strength * 6.0
    state.branches["executive_legislative"] = _clamp(relation, 20.0, 80.0)
    round_label = (
        f"segundo turno ({br_num(result.winner_share, 1)}% a {br_num(result.opponent_share, 1)}%)"
        if result.runoff
        else f"primeiro turno ({br_num(result.winner_share, 1)}%)"
    )
    weights = "; ".join(
        f"{item.text[:48]} ({br_num(item.weight * 100, 0)}%)" for item in result.proposals
    )
    push_history(
        state,
        "system",
        "Vitória nas urnas",
        (
            f"Você venceu a eleição de 2026 no {round_label}, margem de {br_num(result.margin_pp, 1)} p.p. "
            f"A Câmara sai com {congress.chamber.government + congress.chamber.allied} votos na base "
            f"({br_num(congress.coalition_support, 0)}% de coalizão). "
            f"Peso do mandato: {weights}."
        ),
        ["BRA"],
    )
    push_history(
        state,
        "system",
        "Posse presidencial",
        (
            "Janeiro de 2027: você toma posse com mandato das urnas. "
            "A lua de mel existe, mas o orçamento, a Constituição e as próprias promessas de campanha "
            "continuam limitando o que o Palácio pode fazer."
        ),
        ["BRA"],
    )
    state.memory_summary = (
        f"Vitória em 2026 no {round_label}, margem {br_num(result.margin_pp, 1)} p.p. "
        f"Mandato: {weights}. Coalizão inicial {br_num(congress.coalition_support, 0)}%."
    )[:4000]
    return state
