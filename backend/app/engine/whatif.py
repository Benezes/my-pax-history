from __future__ import annotations

from app.constants import INDICATOR_LABELS
from app.engine.congress import pass_chance
from app.engine.costs import compute_cost, verdict
from app.models import (
    ActionProposal,
    AgentPreview,
    AgentReactionProposal,
    EffectPreview,
    GameState,
    WhatIfResult,
)


def _effects(proposal: ActionProposal, scale: float) -> list[EffectPreview]:
    grouped: dict[str, EffectPreview] = {}
    for item in proposal.intended_effects:
        current = grouped.get(item.indicator)
        immediate = item.delta * scale if item.delay_months <= 0 else 0.0
        delayed = item.delta * scale if item.delay_months > 0 else 0.0
        if current is None:
            grouped[item.indicator] = EffectPreview(
                indicator=item.indicator,
                label=INDICATOR_LABELS.get(item.indicator, item.indicator),
                immediate_delta=immediate,
                delayed_delta=delayed,
                delay_months=item.delay_months,
            )
        else:
            current.immediate_delta += immediate
            current.delayed_delta += delayed
            if item.delay_months:
                current.delay_months = max(current.delay_months, item.delay_months)
    return list(grouped.values())


def _agents(
    state: GameState, proposal: ActionProposal, reactions: list[AgentReactionProposal]
) -> list[AgentPreview]:
    previews: list[AgentPreview] = []
    if reactions:
        for reaction in reactions:
            agent = state.agents.get(reaction.agent_id)
            if agent is None:
                continue
            previews.append(
                AgentPreview(
                    agent_id=reaction.agent_id,
                    name=agent.name,
                    action_type=reaction.action_type,
                    statement=reaction.public_statement,
                    stance_delta=reaction.stance_delta,
                )
            )
        return previews
    for agent_id, delta in proposal.agent_pressures.items():
        agent = state.agents.get(agent_id)
        if agent is None:
            continue
        kind = "support" if delta > 0 else "oppose" if delta < 0 else "neutral"
        previews.append(
            AgentPreview(
                agent_id=agent_id,
                name=agent.name,
                action_type=kind,
                statement="",
                stance_delta=delta,
            )
        )
    return previews


def build_what_if(
    state: GameState,
    proposal: ActionProposal,
    raw_text: str,
    commentary: str,
    disagrees: bool,
    reactions: list[AgentReactionProposal] | None = None,
) -> WhatIfResult:
    cost = compute_cost(state, proposal, raw_text)
    resource = verdict(state, cost)
    chance = pass_chance(state, proposal) if resource.mode != "blocked" else 0.0
    timing = proposal.timing_note
    if not timing:
        delays = [e.delay_months for e in proposal.intended_effects if e.delay_months > 0]
        timing = (
            f"Parte dos efeitos aparece em {min(delays)}–{max(delays)} meses."
            if delays
            else "Efeitos principalmente no curto prazo, com risco de reação imediata dos agentes."
        )
    return WhatIfResult(
        title=proposal.title,
        summary=proposal.summary,
        category=proposal.category,
        scope=cost.scope,
        fiscal_cost_brl_bi=cost.fiscal_brl_bi,
        political_cost=cost.political,
        fiscal_available=state.budget.fiscal_space_brl_bi,
        political_available=state.indicators.get("political_capital", 0.0),
        execution=resource.mode,
        scale=resource.scale,
        resource_message=resource.message,
        requires_congress=proposal.requires_congress,
        pass_chance=chance,
        likely_effects=_effects(proposal, resource.scale),
        agent_reactions=_agents(state, proposal, reactions or []),
        risks=list(proposal.risks),
        timing_note=timing,
        advisor_commentary=commentary,
        disagrees=disagrees,
        countries=proposal.affected_countries,
    )
