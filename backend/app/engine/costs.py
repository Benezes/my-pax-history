from __future__ import annotations

from app.constants import DIFFICULTY_PARAMS, FISCAL_COST_BRL_BI, POLITICAL_COST, SCOPE_ORDER
from app.formatters import br_num
from app.models import ActionCost, ActionProposal, GameState, ResourceVerdict


def _index(scope: str) -> int:
    try:
        return SCOPE_ORDER.index(scope)
    except ValueError:
        return 1


def infer_scope(text: str, proposed: str) -> str:
    lowered = text.lower()
    massive = (
        "pacote amplo",
        "reforma ampla",
        "em todo o país",
        "emergencial nacional",
        "trilhão",
        "estado de defesa",
        "estado de sítio",
    )
    large = ("reforma", "pacote", "nacional", "congresso", "constitucional", "ambicioso")
    small = ("sinalizar", "discurso", "anunciar estudo", "um pouco", "modesto", "piloto")
    if any(token in lowered for token in massive):
        return "massive"
    if proposed == "massive":
        return "massive"
    if any(token in lowered for token in large) and proposed in {"small", "medium"}:
        return "large"
    if any(token in lowered for token in small) and proposed in {"medium", "large"}:
        return "small"
    return proposed if proposed in SCOPE_ORDER else "medium"


def compute_cost(state: GameState, proposal: ActionProposal, raw_text: str = "") -> ActionCost:
    scope = infer_scope(raw_text, proposal.scope)
    idx = _index(scope)
    fiscal = FISCAL_COST_BRL_BI.get(proposal.category, FISCAL_COST_BRL_BI["other"])[idx]
    political = POLITICAL_COST.get(proposal.category, POLITICAL_COST["other"])[idx]
    if proposal.requires_congress:
        political += 4.0 + proposal.congress_difficulty * 0.04
        fiscal += 0.8
    multiplier = DIFFICULTY_PARAMS[state.difficulty]["cost_multiplier"]
    fiscal *= multiplier
    political *= multiplier
    if state.indicators["approval"] < 35:
        political *= 1.12
    if state.congress.coalition_support < 40:
        political *= 1.1
    return ActionCost(
        fiscal_brl_bi=round(fiscal, 2),
        political=round(political, 2),
        scope=scope,  # type: ignore[arg-type]
        category=proposal.category,
    )


def verdict(state: GameState, cost: ActionCost) -> ResourceVerdict:
    fiscal_avail = max(0.0, state.budget.fiscal_space_brl_bi)
    political_avail = max(0.0, state.indicators.get("political_capital", 0.0))
    floor = DIFFICULTY_PARAMS[state.difficulty]["partial_floor"]
    fiscal_ratio = 1.0 if cost.fiscal_brl_bi <= 0.05 else fiscal_avail / cost.fiscal_brl_bi
    political_ratio = 1.0 if cost.political <= 0.05 else political_avail / cost.political
    if fiscal_ratio >= 1.0 and political_ratio >= 1.0:
        return ResourceVerdict(
            mode="full",
            scale=1.0,
            fiscal_spent=cost.fiscal_brl_bi,
            political_spent=cost.political,
            message=(
                f"Custo: R$ {br_num(cost.fiscal_brl_bi, 1)} bi de espaço fiscal e "
                f"{br_num(cost.political, 0)} de capital político."
            ),
        )
    scale = min(fiscal_ratio, political_ratio, 1.0)
    if scale < floor:
        reasons: list[str] = []
        if fiscal_ratio < floor:
            reasons.append(
                f"espaço fiscal insuficiente (R$ {br_num(fiscal_avail, 1)} bi disponíveis, "
                f"R$ {br_num(cost.fiscal_brl_bi, 1)} bi necessários)"
            )
        if political_ratio < floor:
            reasons.append(
                f"capital político insuficiente ({br_num(political_avail, 0)} disponíveis, "
                f"{br_num(cost.political, 0)} necessários)"
            )
        joined = " e ".join(reasons)
        return ResourceVerdict(
            mode="blocked",
            scale=0.0,
            fiscal_spent=0.0,
            political_spent=0.0,
            message=f"Ação bloqueada: {joined}. Reduza o escopo ou espere repor recursos.",
        )
    fiscal_spent = min(fiscal_avail, cost.fiscal_brl_bi * scale)
    political_spent = min(political_avail, cost.political * scale)
    return ResourceVerdict(
        mode="partial",
        scale=round(scale, 3),
        fiscal_spent=round(fiscal_spent, 2),
        political_spent=round(political_spent, 2),
        message=(
            f"Ação parcialmente executada ({br_num(scale * 100, 0)}%): os recursos cobrem só parte do custo "
            f"(R$ {br_num(cost.fiscal_brl_bi, 1)} bi e {br_num(cost.political, 0)} de capital). "
            f"Efeitos e alcance foram reduzidos."
        ),
    )


def spend(state: GameState, resource: ResourceVerdict) -> None:
    state.budget.fiscal_space_brl_bi = max(
        0.0, state.budget.fiscal_space_brl_bi - resource.fiscal_spent
    )
    state.budget.year_spent_brl_bi += resource.fiscal_spent
    capital = state.indicators.get("political_capital", 0.0) - resource.political_spent
    state.indicators["political_capital"] = max(0.0, min(100.0, capital))
