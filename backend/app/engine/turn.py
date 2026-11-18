from __future__ import annotations

from datetime import datetime, timezone
from random import Random

from app.constants import AGENT_IDS, GameStatus
from app.engine.apply import (
    apply_delta,
    apply_macro,
    apply_many,
    fire_scheduled,
    format_delta,
    merge_highlights,
    new_id,
    params,
    push_history,
    regenerate_resources,
    schedule,
    sync_derived,
)
from app.engine.congress import roll_vote
from app.engine.costs import compute_cost, spend, verdict
from app.engine.loss import evaluate_loss
from app.models import (
    ActionProposal,
    AgentReactionProposal,
    EventProposal,
    GameState,
    Headline,
    PendingAction,
    ReportSection,
    ResolvedAction,
    TurnLlmBundle,
)


def queue_action(state: GameState, text: str) -> PendingAction:
    pending = PendingAction(id=new_id(), text=text.strip())
    state.pending_actions.append(pending)
    push_history(state, "action", "Ação registrada", text.strip(), ["BRA"])
    return pending


def _unexpected(state: GameState, proposal: ActionProposal, rng: Random, scale: float) -> None:
    p = params(state.difficulty)
    if rng.random() > p["unexpected_chance"]:
        return
    catalog = [
        ("Corrida cambial de curto prazo", {"exchange_rate_usd": 0.18, "approval": -1.4}, ["USA"]),
        ("Vazamento seletivo na imprensa", {"media_climate": -4.5, "approval": -2.0}, ["BRA"]),
        ("Greve-relâmpago em setores-chave", {"gdp_growth": -0.12, "unemployment": 0.08}, ["BRA"]),
        ("Fuga pontual de capitais", {"exchange_rate_usd": 0.12, "public_debt_gdp": 0.25}, ["USA"]),
        ("Judicialização imediata", {"executive_judiciary": -3.5, "institutional_stability": -2.0}, ["BRA"]),
    ]
    if proposal.category == "security":
        catalog.append(
            ("Denúncia de abuso operacional", {"media_climate": -5.0, "stf": 0.0}, ["BRA"])
        )
    title, deltas, countries = rng.choice(catalog)
    cleaned = {k: v * scale * p["consequence_intensity"] for k, v in deltas.items() if k != "stf"}
    apply_many(state, cleaned, p["consequence_intensity"])
    push_history(state, "event", "Consequência inesperada: " + title, "Efeito de curto prazo não previsto no desenho da medida.", countries, {"unexpected": True})
    merge_highlights(state, countries)
    if rng.random() < p["secondary_problem_chance"]:
        state.scandals += 0.35 * p["agent_hostility"]


def _anticipation(state: GameState, proposal: ActionProposal, rng: Random) -> None:
    p = params(state.difficulty)
    if rng.random() > p["anticipation"]:
        return
    threatened = [
        agent_id
        for agent_id, delta in proposal.agent_pressures.items()
        if delta < 0 and agent_id in state.agents
    ]
    if not threatened:
        threatened = ["congresso", "imprensa"]
    agent_id = rng.choice(threatened)
    agent = state.agents[agent_id]
    agent.stance = max(-100.0, agent.stance - 4.0 * p["agent_hostility"])
    if agent_id == "empresariado":
        apply_delta(state, "exchange_rate_usd", 0.08, p["consequence_intensity"])
    if agent_id == "congresso":
        apply_delta(state, "coalition_support", -2.2, p["consequence_intensity"])
    push_history(
        state,
        "agent",
        f"{agent.name} antecipa o movimento",
        f"{agent.name} age antes da medida se consolidar, protegendo interesses próprios.",
        ["BRA"],
    )


def _apply_proposal(
    state: GameState, proposal: ActionProposal, raw_text: str, rng: Random
) -> ResolvedAction:
    p = params(state.difficulty)
    cost = compute_cost(state, proposal, raw_text)
    resource = verdict(state, cost)
    if resource.mode == "blocked":
        push_history(state, "resource", "Ação bloqueada por falta de recursos", resource.message, ["BRA"])
        return ResolvedAction(
            title=proposal.title,
            summary=proposal.summary,
            passed=False,
            reason=resource.message,
            category=proposal.category,
            execution="blocked",
            scale=0.0,
            fiscal_cost_brl_bi=cost.fiscal_brl_bi,
            political_cost=cost.political,
            countries=proposal.affected_countries,
        )
    spend(state, resource)
    passed, vote_reason, _chance = roll_vote(state, proposal, rng)
    if resource.mode == "partial":
        vote_reason = resource.message + " " + vote_reason
    if not passed:
        state.budget.fiscal_space_brl_bi = min(
            state.budget.fiscal_space_annual_cap_brl_bi,
            state.budget.fiscal_space_brl_bi + resource.fiscal_spent,
        )
        state.budget.year_spent_brl_bi = max(0.0, state.budget.year_spent_brl_bi - resource.fiscal_spent)
        apply_delta(state, "political_capital", -2.5, 1.0)
        apply_delta(state, "coalition_support", -1.8, p["consequence_intensity"])
        apply_delta(state, "media_climate", -2.0, 1.0)
        push_history(state, "action_result", f"Derrota: {proposal.title}", vote_reason, ["BRA"])
        return ResolvedAction(
            title=proposal.title,
            summary=proposal.summary,
            passed=False,
            reason=vote_reason + " O espaço fiscal não foi empenhado.",
            category=proposal.category,
            execution=resource.mode,
            scale=resource.scale,
            fiscal_cost_brl_bi=0.0,
            political_cost=resource.political_spent,
            countries=proposal.affected_countries,
        )
    scale = resource.scale
    immediate: dict[str, float] = {}
    for item in proposal.intended_effects:
        scaled = item.delta * scale * (0.55 + item.confidence * 0.45)
        if item.delay_months <= 0:
            immediate[item.indicator] = immediate.get(item.indicator, 0.0) + scaled
        else:
            slippage = 1.0
            if rng.random() < p["delayed_slippage"]:
                slippage = rng.uniform(0.55, 0.9)
                push_history(
                    state,
                    "system",
                    "Atraso na implementação",
                    f"{proposal.title}: a burocracia e o Congresso diluíram parte do efeito previsto.",
                    ["BRA"],
                )
            schedule(
                state,
                proposal.title,
                {item.indicator: scaled * slippage},
                item.delay_months,
                proposal.title,
                unexpected=False,
                countries=proposal.affected_countries,
            )
    applied = apply_many(state, immediate, p["consequence_intensity"])
    for agent_id, pressure in proposal.agent_pressures.items():
        agent = state.agents.get(agent_id)
        if agent is None:
            continue
        hostility = p["agent_hostility"] if pressure < 0 else 1.0
        agent.stance = max(-100.0, min(100.0, agent.stance + pressure * scale * hostility * 0.35))
    merge_highlights(state, proposal.affected_countries or ["BRA"])
    _unexpected(state, proposal, rng, scale)
    _anticipation(state, proposal, rng)
    parts = [format_delta(k, v) for k, v in applied.items() if abs(v) > 0.01]
    body = resource.message + " " + vote_reason
    if parts:
        body += " Efeitos imediatos: " + "; ".join(parts) + "."
    push_history(state, "action_result", proposal.title, body, proposal.affected_countries or ["BRA"])
    return ResolvedAction(
        title=proposal.title,
        summary=proposal.summary,
        passed=True,
        reason=body,
        category=proposal.category,
        execution=resource.mode,
        scale=resource.scale,
        fiscal_cost_brl_bi=resource.fiscal_spent,
        political_cost=resource.political_spent,
        countries=proposal.affected_countries,
    )


def _reactions(state: GameState, reactions: list[AgentReactionProposal], rng: Random) -> None:
    p = params(state.difficulty)
    seen: set[str] = set()
    for reaction in reactions:
        if reaction.agent_id in seen or reaction.agent_id not in state.agents:
            continue
        seen.add(reaction.agent_id)
        agent = state.agents[reaction.agent_id]
        hostility = p["agent_hostility"] if reaction.stance_delta < 0 else 0.85
        agent.stance = max(-100.0, min(100.0, agent.stance + reaction.stance_delta * hostility * 0.5))
        agent.resources = max(0.0, min(100.0, agent.resources - abs(reaction.resource_spend) * 0.2))
        extra = {}
        for item in reaction.extra_effects:
            extra[item.indicator] = extra.get(item.indicator, 0.0) + cap_effect(item.delta, p)
        if extra:
            apply_many(state, extra, p["consequence_intensity"])
        push_history(
            state,
            "agent",
            f"{agent.name}: {reaction.action_type}",
            reaction.public_statement,
            ["BRA"],
        )
        if reaction.action_type == "investigate":
            state.scandals += 0.4 * p["agent_hostility"]
            apply_delta(state, "media_climate", -2.5, 1.0)
    for agent_id in AGENT_IDS:
        if agent_id in seen:
            continue
        agent = state.agents[agent_id]
        drift = rng.uniform(-1.2, 1.2) * (0.6 + p["anticipation"] * 0.4)
        agent.stance = max(-100.0, min(100.0, agent.stance + drift))


def cap_effect(delta: float, p: dict[str, float]) -> float:
    return max(-8.0, min(8.0, delta)) * 0.45 * p["consequence_intensity"]


def _events(state: GameState, events: list[EventProposal], rng: Random) -> None:
    p = params(state.difficulty)
    for event in events[:4]:
        severity = max(1, min(5, event.severity + int(p["event_severity_bias"])))
        factor = (0.55 + severity * 0.12) * p["foreign_pressure"]
        immediate = {}
        for item in event.suggested_effects:
            immediate[item.indicator] = immediate.get(item.indicator, 0.0) + item.delta * factor
        apply_many(state, immediate, p["consequence_intensity"])
        for item in event.delayed_effects:
            schedule(
                state,
                event.title,
                {item.indicator: item.delta * factor},
                max(1, item.delay_months),
                event.title,
                unexpected=False,
                countries=event.countries,
            )
        countries = event.countries or ["BRA"]
        merge_highlights(state, countries)
        push_history(state, "event", event.title, event.narrative, countries, {"severity": severity})
        tone = "negative" if severity >= 4 else "neutral" if severity == 3 else "positive"
        state.headlines.append(
            Headline(
                id=new_id(),
                month_index=state.date.month_index(),
                outlet="Agência Brasil" if event.scope == "national" else "Cabo diplomático",
                title=event.title,
                tone=tone,  # type: ignore[arg-type]
                reach=min(1.5, 0.4 + severity * 0.2),
            )
        )
        state.headlines = state.headlines[-30:]
        if event.scope == "international":
            for iso in event.countries:
                if iso in state.powers:
                    shock = rng.uniform(-2.5, 1.2) * p["foreign_pressure"]
                    power = state.powers[iso]
                    power.relation_brazil = max(0.0, min(100.0, power.relation_brazil + shock * 0.3))
                    state.diplomacy[iso] = power.relation_brazil
                elif iso in state.diplomacy:
                    state.diplomacy[iso] = max(
                        0.0, min(100.0, state.diplomacy[iso] + rng.uniform(-2.0, 1.5))
                    )


def _world_drift(state: GameState, rng: Random) -> None:
    p = params(state.difficulty)
    for power in state.powers.values():
        power.stability = max(5.0, min(95.0, power.stability + rng.uniform(-1.4, 1.1) * p["foreign_pressure"]))
        power.gdp_growth += rng.uniform(-0.08, 0.08)
        if power.iso == "USA" and rng.random() < 0.12 * p["foreign_pressure"]:
            apply_delta(state, "exchange_rate_usd", rng.uniform(-0.05, 0.12), p["consequence_intensity"])
        if power.iso == "CHN" and rng.random() < 0.1 * p["foreign_pressure"]:
            apply_delta(state, "gdp_growth", rng.uniform(-0.06, 0.05), p["consequence_intensity"])
        state.diplomacy[power.iso] = power.relation_brazil


def _fallback_report(state: GameState, resolved: list[ResolvedAction]) -> ReportSection:
    blocked = [item for item in resolved if item.execution == "blocked"]
    partial = [item for item in resolved if item.execution == "partial"]
    passed = [item for item in resolved if item.passed]
    problems = sorted(state.problems, key=lambda item: item.severity, reverse=True)[:3]
    problem_text = "; ".join(f"{item.title} (gravidade {item.severity:.0f})" for item in problems)
    consequencias = "Nenhuma decisão presidencial neste mês."
    if passed:
        consequencias = "Decisões aplicadas: " + "; ".join(item.title for item in passed) + "."
    if partial:
        consequencias += " Algumas medidas saíram pela metade por falta de recursos."
    if blocked:
        consequencias += " Medidas bloqueadas: " + "; ".join(item.title for item in blocked) + "."
    return ReportSection(
        economia=(
            f"Selic em {state.indicators['selic']:.2f}%, inflação {state.indicators['inflation']:.2f}%, "
            f"PIB {state.indicators['gdp_growth']:+.2f}%, dívida {state.indicators['public_debt_gdp']:.1f}% do PIB. "
            f"Espaço fiscal: R$ {state.budget.fiscal_space_brl_bi:.1f} bi."
        ),
        politica=(
            f"Apoio da coalizão em {state.congress.coalition_support:.0f}%. "
            f"Relação Executivo–Legislativo: {state.branches.get('executive_legislative', 0):.0f}. "
            f"Capital político: {state.indicators['political_capital']:.0f}."
        ),
        seguranca=(
            f"Índice de criminalidade em {state.indicators['crime_index']:.0f}. "
            f"Estabilidade institucional: {state.indicators['institutional_stability']:.0f}."
        ),
        aprovacao=f"Aprovação presidencial em {state.indicators['approval']:.1f}%.",
        relacoes_internacionais=(
            "Relações: "
            + ", ".join(
                f"{power.name} {power.relation_brazil:.0f}"
                for power in list(state.powers.values())[:5]
            )
            + "."
        ),
        consequencias=consequencias,
        problemas=problem_text or "Nenhum foco crítico adicional.",
    )


def process_month(state: GameState, bundle: TurnLlmBundle, rng: Random) -> None:
    if state.status != GameStatus.PLAYING:
        return
    texts = [item.text for item in state.pending_actions]
    combined = "\n".join(texts)
    proposals = bundle.interpretation.actions
    if not proposals and texts:
        proposals = [
            ActionProposal(
                title="Agenda presidencial",
                summary=combined[:400],
                category="other",
                scope="medium",
            )
        ]
    resolved: list[ResolvedAction] = []
    for index, proposal in enumerate(proposals):
        raw = texts[index] if index < len(texts) else combined
        resolved.append(_apply_proposal(state, proposal, raw, rng))
    state.pending_actions = []
    state.last_resolved = resolved
    _reactions(state, bundle.reactions, rng)
    apply_macro(state, rng)
    fire_scheduled(state)
    _events(state, bundle.events, rng)
    _world_drift(state, rng)
    regenerate_resources(state)
    sync_derived(state)
    evaluate_loss(state)
    facts = _fallback_report(state, resolved)
    llm_report = bundle.report
    report = ReportSection(
        economia=facts.economia,
        politica=facts.politica,
        seguranca=facts.seguranca,
        aprovacao=facts.aprovacao,
        relacoes_internacionais=facts.relacoes_internacionais,
        consequencias=llm_report.consequencias or facts.consequencias,
        problemas=llm_report.problemas or facts.problemas,
    )
    state.last_report = report
    if bundle.memory_update:
        state.memory_summary = (state.memory_summary + " " + bundle.memory_update).strip()[-4000:]
    push_history(
        state,
        "report",
        f"Relatório — {state.date.label()}",
        report.problemas or report.consequencias or "Ciclo mensal concluído.",
        state.highlighted_countries[:6],
    )
    state.months_elapsed += 1
    state.date = state.date.advance(1)
    state.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


def advance_months(state: GameState, bundles: list[TurnLlmBundle]) -> GameState:
    rng = Random(state.seed + state.months_elapsed * 17)
    for bundle in bundles:
        if state.status != GameStatus.PLAYING:
            break
        process_month(state, bundle, rng)
        rng = Random(state.seed + state.months_elapsed * 17)
    return state
