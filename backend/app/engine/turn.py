from __future__ import annotations

from datetime import datetime, timezone
from random import Random

from app.constants import AGENT_IDS, REJECTION_CAPITAL_REFUND, GameStatus
from app.formatters import agent_verb, br_num
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
from app.engine.congress import roll_vote, stamp_amendment
from app.engine.costs import compute_cost, spend, verdict
from app.engine.mandate import assess_mandate, unconstitutional_reason
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
        f"{agent.name} {agent_verb(agent_id, 'antecipa', 'antecipam')} o movimento",
        f"{agent.name} {agent_verb(agent_id, 'age', 'agem')} antes da medida se consolidar, protegendo interesses próprios.",
        ["BRA"],
    )


def _blocked(
    proposal: ActionProposal,
    reason: str,
    cost_political: float = 0.0,
    cost_fiscal: float = 0.0,
    mandate_note: str = "",
    mandate_applied: bool = False,
    limit_kind: str = "budget",
) -> ResolvedAction:
    extra = f" {mandate_note}" if mandate_note else ""
    return ResolvedAction(
        title=proposal.title,
        summary=proposal.summary,
        passed=False,
        reason=reason + extra,
        category=proposal.category,
        execution="blocked",
        scale=0.0,
        fiscal_cost_brl_bi=cost_fiscal,
        political_cost=cost_political,
        countries=proposal.affected_countries,
        mandate_applied=mandate_applied,
        mandate_note=mandate_note,
        limit_kind=limit_kind,
    )


def _apply_proposal(
    state: GameState, proposal: ActionProposal, raw_text: str, rng: Random
) -> ResolvedAction:
    p = params(state.difficulty)
    mandate = assess_mandate(state, raw_text, proposal)
    illegal = unconstitutional_reason(raw_text)
    if illegal:
        note = (
            " O bônus do mandato das urnas não se aplica a medidas inconstitucionais."
            if mandate.matched
            else ""
        )
        push_history(state, "resource", "Ação bloqueada", illegal, ["BRA"])
        return _blocked(proposal, illegal + note, mandate_note=mandate.note, limit_kind="constitution")
    if mandate.contradicts:
        push_history(state, "resource", "Ação bloqueada pelo mandato", mandate.contradict_reason, ["BRA"])
        return _blocked(
            proposal,
            mandate.contradict_reason,
            mandate_note=mandate.note,
            limit_kind="campaign",
        )
    cost = compute_cost(state, proposal, raw_text, mandate)
    resource = verdict(state, cost)
    if resource.mode == "blocked":
        would = (
            " Sem o limite orçamentário, o mandato das urnas teria barateado o capital político."
            if mandate.applied
            else ""
        )
        reason = resource.message + would
        if mandate.applied:
            reason += " " + mandate.note
        push_history(state, "resource", "Ação bloqueada por falta de recursos", reason, ["BRA"])
        return _blocked(
            proposal,
            reason,
            cost_political=cost.political,
            cost_fiscal=cost.fiscal_brl_bi,
            mandate_note=mandate.note,
            mandate_applied=False,
            limit_kind="budget",
        )
    stamp_amendment(proposal, raw_text)
    spend(state, resource)
    passed, vote_reason, _chance = roll_vote(state, proposal, rng, mandate)
    if mandate.applied:
        vote_reason = vote_reason + " " + mandate.note
    if not passed:
        state.budget.fiscal_space_brl_bi = min(
            state.budget.fiscal_space_annual_cap_brl_bi,
            state.budget.fiscal_space_brl_bi + resource.fiscal_spent,
        )
        state.budget.year_spent_brl_bi = max(0.0, state.budget.year_spent_brl_bi - resource.fiscal_spent)
        refund = round(resource.political_spent * REJECTION_CAPITAL_REFUND, 2)
        if refund > 0:
            capital = state.indicators.get("political_capital", 0.0) + refund
            state.indicators["political_capital"] = max(0.0, min(100.0, capital))
        apply_delta(state, "political_capital", -2.5, 1.0)
        apply_delta(state, "coalition_support", -1.8, p["consequence_intensity"])
        apply_delta(state, "media_climate", -2.0, 1.0)
        apply_delta(state, "approval", -1.5, p["consequence_intensity"])
        refund_note = (
            f" O Congresso rejeitou a medida; o espaço fiscal não foi empenhado. "
            f"Foram devolvidos {br_num(refund, 1)} de capital político "
            f"({br_num(REJECTION_CAPITAL_REFUND * 100, 0)}% do custo cobrado)."
        )
        reason = vote_reason + refund_note
        push_history(state, "action_result", f"Derrota: {proposal.title}", reason, ["BRA"])
        return ResolvedAction(
            title=proposal.title,
            summary=proposal.summary,
            passed=False,
            reason=reason,
            category=proposal.category,
            execution="rejected",
            scale=0.0,
            fiscal_cost_brl_bi=0.0,
            political_cost=max(0.0, resource.political_spent - refund),
            countries=proposal.affected_countries,
            mandate_applied=mandate.applied,
            mandate_note=mandate.note,
            capital_refunded=refund,
            limit_kind="congress",
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
        mandate_applied=mandate.applied,
        mandate_note=mandate.note,
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


def _approval_narrative(
    state: GameState,
    resolved: list[ResolvedAction],
    approval_before: float | None = None,
    delayed_approval: bool = False,
) -> str:
    now = float(state.indicators["approval"])
    rejected = [item for item in resolved if item.execution == "rejected"]
    text = f"Aprovação presidencial em {br_num(now, 1)}%."
    if approval_before is None:
        return text + (" Derrotas no Congresso desgastam a popularidade." if rejected else "")
    delta = now - approval_before
    if abs(delta) >= 0.05:
        verb = "subiu" if delta > 0 else "recuou"
        text += f" A popularidade {verb} {br_num(abs(delta), 1)} p.p."
    if delayed_approval and delta > 0.05:
        text += " O avanço inclui efeito defasado de medidas anteriores."
    elif rejected and delta < -0.05:
        text += " Derrotas no Congresso desgastam a popularidade."
    elif rejected and delta > 0.05:
        text += " Apesar das derrotas no Congresso, a popularidade avançou."
    return text


def _fallback_report(
    state: GameState,
    resolved: list[ResolvedAction],
    approval_before: float | None = None,
    delayed_approval: bool = False,
) -> ReportSection:
    blocked = [item for item in resolved if item.execution == "blocked"]
    rejected = [item for item in resolved if item.execution == "rejected"]
    partial = [item for item in resolved if item.passed and item.execution == "partial"]
    passed = [item for item in resolved if item.passed]
    problems = sorted(state.problems, key=lambda item: item.severity, reverse=True)[:3]
    problem_text = "; ".join(f"{item.title} (gravidade {br_num(item.severity, 0)})" for item in problems)
    parts: list[str] = []
    if passed:
        parts.append("Decisões aplicadas: " + "; ".join(item.title for item in passed) + ".")
    if rejected:
        parts.append(
            "O Congresso rejeitou: "
            + "; ".join(item.title for item in rejected)
            + ". Nenhum espaço fiscal foi empenhado."
        )
    if partial:
        parts.append("Algumas medidas saíram pela metade por falta de recursos.")
    if blocked:
        parts.append("Medidas bloqueadas: " + "; ".join(item.title for item in blocked) + ".")
    consequencias = " ".join(parts) if parts else "Nenhuma decisão presidencial neste mês."
    return ReportSection(
        economia=(
            f"Selic em {br_num(state.indicators['selic'], 2)}%, inflação {br_num(state.indicators['inflation'], 2)}%, "
            f"PIB {br_num(state.indicators['gdp_growth'], 2, signed=True)}%, "
            f"dívida {br_num(state.indicators['public_debt_gdp'], 1)}% do PIB. "
            f"Espaço fiscal: R$ {br_num(state.budget.fiscal_space_brl_bi, 1)} bi "
            f"(a arrecadação recompôs cerca de R$ {br_num(state.budget.monthly_replenish_brl_bi, 1)} bi neste mês)."
        ),
        politica=(
            f"Apoio da coalizão em {br_num(state.congress.coalition_support, 0)}%. "
            f"Relação Executivo–Legislativo: {br_num(state.branches.get('executive_legislative', 0), 0)}. "
            f"Capital político: {br_num(state.indicators['political_capital'], 0)}."
        ),
        seguranca=(
            f"Índice de criminalidade em {br_num(state.indicators['crime_index'], 0)}. "
            f"Estabilidade institucional: {br_num(state.indicators['institutional_stability'], 0)}."
        ),
        aprovacao=_approval_narrative(state, resolved, approval_before, delayed_approval),
        relacoes_internacionais=(
            "Relações: "
            + ", ".join(
                f"{power.name} {br_num(power.relation_brazil, 0)}"
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
    approval_before = float(state.indicators.get("approval", 0.0))
    month_index = state.date.month_index()
    delayed_approval = any(
        effect.fire_month_index <= month_index and abs(effect.deltas.get("approval", 0.0)) > 0.01
        for effect in state.scheduled_effects
    )
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
    facts = _fallback_report(state, resolved, approval_before, delayed_approval)
    llm_report = bundle.report
    report = ReportSection(
        economia=facts.economia,
        politica=facts.politica,
        seguranca=facts.seguranca,
        aprovacao=facts.aprovacao,
        relacoes_internacionais=facts.relacoes_internacionais,
        consequencias=facts.consequencias,
        problemas=facts.problemas or llm_report.problemas,
    )
    state.last_report = report
    if bundle.memory_update:
        state.memory_summary = (state.memory_summary + " " + bundle.memory_update).strip()[-4000:]
    state.months_elapsed += 1
    if state.status == GameStatus.PLAYING:
        state.date = state.date.advance(1)
    push_history(
        state,
        "report",
        f"Relatório — {state.date.label()}",
        report.consequencias or report.problemas or "Ciclo mensal concluído.",
        state.highlighted_countries[:6],
    )
    state.updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


def advance_months(state: GameState, bundles: list[TurnLlmBundle]) -> GameState:
    rng = Random(state.seed + state.months_elapsed * 17)
    for bundle in bundles:
        if state.status != GameStatus.PLAYING:
            break
        process_month(state, bundle, rng)
        rng = Random(state.seed + state.months_elapsed * 17)
    return state
