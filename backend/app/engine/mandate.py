from __future__ import annotations

import re
from dataclasses import dataclass

from app.constants import (
    MANDATE_CAPITAL_CUT_MAX,
    MANDATE_CAPITAL_REDUCTION,
    MANDATE_LLM_MIN_ENGINE,
    MANDATE_MATCH_THRESHOLD,
    MANDATE_PASS_BONUS,
    MANDATE_PASS_BOOST_MAX,
    MANDATE_POPULARITY_FLOOR,
    MANDATE_YEAR1_CAPITAL_FLOOR,
    MANDATE_YEAR1_PASS_FLOOR,
    MANDATE_YEAR_DECAY,
    UNCONSTITUTIONAL_TOKENS,
)
from app.formatters import br_num
from app.models import ActionProposal, CampaignMandateItem, GameState

_STOP = frozenset(
    {
        "para",
        "como",
        "uma",
        "uns",
        "umas",
        "pelo",
        "pela",
        "mais",
        "menos",
        "sobre",
        "entre",
        "com",
        "sem",
        "dos",
        "das",
        "que",
        "nao",
        "não",
        "por",
        "the",
        "and",
    }
)

CONTRADICT_PAIRS = (
    (
        ("responsabilidade fiscal", "ajuste fiscal", "teto de gastos", "equilíbrio fiscal"),
        ("imprimir dinheiro", "gastar sem limite", "furar o teto", "estouro fiscal"),
    ),
    (
        ("democracia", "respeito ao congresso", "pacto democrático", "estado de direito"),
        ("fechar o congresso", "golpe", "autogolpe", "fechar o stf", "ditadura"),
    ),
    (
        ("paz", "direitos humanos", "civil"),
        ("intervenção militar", "ai-5", "ai5", "estado de sítio"),
    ),
)


def tokenize(text: str) -> set[str]:
    folded = (
        (text or "")
        .lower()
        .replace("á", "a")
        .replace("à", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    tokens = re.findall(r"[a-z0-9]{4,}", folded)
    return {token for token in tokens if token not in _STOP}


def overlap_score(action_text: str, item: CampaignMandateItem) -> float:
    action_tokens = tokenize(action_text)
    if not action_tokens:
        return 0.0
    mandate_tokens = tokenize(item.text) | tokenize(" ".join(item.keywords)) | tokenize(item.summary)
    if not mandate_tokens:
        return 0.0
    hits = action_tokens & mandate_tokens
    jaccard = len(hits) / max(1, len(action_tokens | mandate_tokens))
    coverage = len(hits) / max(1, len(action_tokens))
    lowered = action_text.lower()
    keyword_hits = sum(1 for key in item.keywords if key and key.lower() in lowered)
    keyword_boost = min(0.35, keyword_hits * 0.12)
    return min(1.0, jaccard * 0.55 + coverage * 0.45 + keyword_boost)


def year_decay(months_elapsed: int) -> float:
    year = max(0, min(3, months_elapsed // 12))
    return MANDATE_YEAR_DECAY[year]


def popularity_factor(approval: float) -> float:
    return max(MANDATE_POPULARITY_FLOOR, min(1.2, 0.4 + approval / 100.0))


def unconstitutional_reason(text: str) -> str | None:
    lowered = (text or "").lower()
    for token in UNCONSTITUTIONAL_TOKENS:
        if token in lowered:
            return (
                f"Ação bloqueada por limite constitucional: o texto envolve «{token}», "
                "incompatível com a ordem democrática."
            )
    return None


def campaign_contradiction(action_text: str, items: list[CampaignMandateItem]) -> str | None:
    lowered = (action_text or "").lower()
    joined = " ".join(item.text.lower() for item in items)
    for campaign_keys, action_keys in CONTRADICT_PAIRS:
        if any(key in joined for key in campaign_keys) and any(key in lowered for key in action_keys):
            return (
                "Ação bloqueada porque contradiz o mandato das urnas: a campanha prometeu "
                f"«{campaign_keys[0]}», e esta medida aponta para «{action_keys[0]}»."
            )
    return None


@dataclass
class MandateAssessment:
    matched: bool
    contradicts: bool
    bonus: float
    proposal_id: str = ""
    proposal_text: str = ""
    match_score: float = 0.0
    year_factor: float = 1.0
    popularity_factor: float = 1.0
    capital_cut: float = 0.0
    pass_boost: float = 0.0
    note: str = ""
    contradict_reason: str = ""
    limit_kind: str = ""

    @property
    def applied(self) -> bool:
        return self.matched and not self.contradicts and self.bonus > 0.02


def assess_mandate(state: GameState, raw_text: str, proposal: ActionProposal | None = None) -> MandateAssessment:
    empty = MandateAssessment(matched=False, contradicts=False, bonus=0.0)
    campaign = state.campaign
    if campaign is None or not campaign.proposals:
        return empty
    contradiction = campaign_contradiction(raw_text, campaign.proposals)
    if contradiction:
        return MandateAssessment(
            matched=False,
            contradicts=True,
            bonus=0.0,
            contradict_reason=contradiction,
            note=contradiction,
            limit_kind="campaign",
        )
    scored = [(overlap_score(raw_text, item), item) for item in campaign.proposals]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    best_score, best = scored[0]
    llm_score = 0.0
    if proposal is not None:
        llm_score = max(0.0, min(1.0, proposal.mandate_hint_score or 0.0))
        if proposal.contradicts_campaign and best_score >= MANDATE_LLM_MIN_ENGINE:
            reason = (
                "Ação bloqueada porque contradiz uma proposta da campanha "
                f"(«{best.text[:80]}»)."
            )
            return MandateAssessment(
                matched=False,
                contradicts=True,
                bonus=0.0,
                proposal_id=best.id,
                proposal_text=best.text,
                match_score=best_score,
                contradict_reason=reason,
                note=reason,
                limit_kind="campaign",
            )
        hint_index = proposal.mandate_hint_index
        if hint_index is not None and 0 <= hint_index < len(campaign.proposals):
            hinted = campaign.proposals[hint_index]
            hinted_score = overlap_score(raw_text, hinted)
            if hinted_score >= MANDATE_LLM_MIN_ENGINE and hinted_score + 0.05 >= best_score:
                best = hinted
                best_score = max(best_score, hinted_score)
    matched = best_score >= MANDATE_MATCH_THRESHOLD or (
        llm_score >= 0.55 and best_score >= MANDATE_LLM_MIN_ENGINE
    )
    if not matched:
        return MandateAssessment(matched=False, contradicts=False, bonus=0.0, match_score=best_score)
    year_factor = year_decay(state.months_elapsed)
    pop_factor = popularity_factor(state.indicators.get("approval", 50.0))
    margin = 0.0
    if campaign is not None:
        margin = max(0.0, float(campaign.margin_pp))
    margin_factor = max(0.75, min(1.15, 0.75 + margin / 40.0))
    weight_term = 0.72 + 0.28 * max(0.0, min(1.0, best.weight))
    bonus = max(0.0, min(1.0, year_factor * pop_factor * weight_term * margin_factor))
    capital_cut = MANDATE_CAPITAL_REDUCTION * bonus
    pass_boost = MANDATE_PASS_BONUS * bonus
    if year_factor >= 0.99:
        capital_cut = max(capital_cut, MANDATE_YEAR1_CAPITAL_FLOOR + 0.12 * best.weight)
        pass_boost = max(pass_boost, MANDATE_YEAR1_PASS_FLOOR + 0.08 * best.weight)
    capital_cut = max(0.0, min(MANDATE_CAPITAL_CUT_MAX, capital_cut))
    pass_boost = max(0.0, min(MANDATE_PASS_BOOST_MAX, pass_boost))
    note = (
        f"Mandato das urnas: bônus aplicado na proposta «{best.text[:90]}» "
        f"(peso {br_num(best.weight * 100, 0)}%, fator do ano {br_num(year_factor * 100, 0)}%). "
        f"Capital político {br_num(capital_cut * 100, 0)}% mais barato; "
        f"chance no Congresso +{br_num(pass_boost * 100, 0)} p.p."
    )
    return MandateAssessment(
        matched=True,
        contradicts=False,
        bonus=bonus,
        proposal_id=best.id,
        proposal_text=best.text,
        match_score=best_score,
        year_factor=year_factor,
        popularity_factor=pop_factor,
        capital_cut=capital_cut,
        pass_boost=pass_boost,
        note=note,
    )


def mandate_cost_factor(assessment: MandateAssessment) -> float:
    if not assessment.applied:
        return 1.0
    return max(0.65, 1.0 - assessment.capital_cut)


def mandate_pass_delta(assessment: MandateAssessment) -> float:
    if not assessment.applied:
        return 0.0
    return assessment.pass_boost
