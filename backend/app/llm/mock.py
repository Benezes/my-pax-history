from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from app.constants import MANDATE_LLM_MIN_ENGINE, ProviderId
from app.engine.mandate import overlap_score
from app.formatters import agent_verb, br_num, tidy_pt
from app.llm.base import LlmProvider
from app.models import (
    ActionInterpretation,
    ActionProposal,
    AdvisorReply,
    AgentReactionProposal,
    CampaignClassification,
    CampaignProposalHint,
    EventProposal,
    GameState,
    IndicatorDelta,
    ReportSection,
    TurnLlmBundle,
)


@dataclass(frozen=True)
class PolicyPattern:
    keywords: tuple[str, ...]
    title: str
    category: str
    scope: str
    requires_congress: bool
    congress_difficulty: int
    effects: tuple[tuple[str, float, int], ...]
    agents: dict[str, float]
    countries: tuple[str, ...]
    risks: tuple[str, ...]
    timing: str
    summary: str


POLICIES = (
    PolicyPattern(
        keywords=("reforma tributária", "reforma tributaria", "iva", "imposto", "tribut"),
        title="Reforma tributária",
        category="fiscal",
        scope="large",
        requires_congress=True,
        congress_difficulty=58,
        effects=(
            ("approval", -3.2, 0),
            ("gdp_growth", 0.28, 10),
            ("public_debt_gdp", -1.1, 16),
            ("empresariado", 0.0, 0),
        ),
        agents={"empresariado": 7, "sindicatos": -5, "congresso": -6, "governadores": -3},
        countries=("BRA",),
        risks=("Centrão cobra emendas", "Transição tributária gera incerteza de curto prazo"),
        timing="Custo político imediato; ganho de crescimento em 10–16 meses.",
        summary="Proposta de reorganização tributária com impacto fiscal de médio prazo.",
    ),
    PolicyPattern(
        keywords=("infraestrutura", "infra", "obra", "ferrovia", "porto", "saneamento"),
        title="Pacote de infraestrutura",
        category="infra",
        scope="large",
        requires_congress=True,
        congress_difficulty=58,
        effects=(
            ("infrastructure_index", 2.4, 8),
            ("gdp_growth", 0.22, 9),
            ("public_debt_gdp", 0.9, 0),
            ("unemployment", -0.18, 10),
        ),
        agents={"governadores": 8, "empresariado": 6, "congresso": 3, "sociedade_civil": 2},
        countries=("BRA",),
        risks=("Estouro de custo em obras", "Licitação lenta"),
        timing="Dívida sobe agora; obras aparecem em 8–12 meses.",
        summary="Investimento público em logística e saneamento.",
    ),
    PolicyPattern(
        keywords=("selic", "juros", "copom", "política monetária", "politica monetaria"),
        title="Orientação de política monetária",
        category="monetary",
        scope="medium",
        requires_congress=False,
        congress_difficulty=20,
        effects=(
            ("selic", -0.5, 0),
            ("inflation", 0.15, 3),
            ("gdp_growth", 0.12, 4),
            ("approval", 1.2, 2),
        ),
        agents={"empresariado": 5, "sindicatos": 3, "imprensa": -1},
        countries=("BRA", "USA"),
        risks=("Desancoragem de expectativas", "Pressão do Banco Central por autonomia"),
        timing="Juros reagem no mês; inflação em 3 meses.",
        summary="Sinalização para ciclo de juros, sem romper a autonomia formal do BC.",
    ),
    PolicyPattern(
        keywords=("saúde", "saude", "sus", "hospital", "vacina"),
        title="Reforço da saúde pública",
        category="social",
        scope="medium",
        requires_congress=True,
        congress_difficulty=48,
        effects=(("health_index", 2.1, 6), ("approval", 1.8, 2), ("poverty", -0.2, 8)),
        agents={"sociedade_civil": 6, "sindicatos": 4, "congresso": -2},
        countries=("BRA",),
        risks=("Filas continuam no curto prazo", "Estados cobram transferências"),
        timing="Aprovação em 2 meses; qualidade assistencial em 6.",
        summary="Expansão pontual de gasto em saúde.",
    ),
    PolicyPattern(
        keywords=("educação", "educacao", "escola", "universidade", "professor"),
        title="Agenda educacional",
        category="social",
        scope="medium",
        requires_congress=True,
        congress_difficulty=50,
        effects=(("education_index", 1.8, 10), ("approval", 1.0, 3)),
        agents={"sociedade_civil": 5, "sindicatos": 6, "empresariado": 1},
        countries=("BRA",),
        risks=("Resultado só aparece no médio prazo",),
        timing="Indicador educacional em cerca de 10 meses.",
        summary="Política educacional de maturação lenta.",
    ),
    PolicyPattern(
        keywords=("segurança", "seguranca", "crime", "polícia", "policia", "pcc", "facção", "faccao"),
        title="Plano de segurança pública",
        category="security",
        scope="large",
        requires_congress=True,
        congress_difficulty=55,
        effects=(
            ("crime_index", -2.4, 5),
            ("approval", 2.2, 1),
            ("institutional_stability", -1.2, 0),
            ("media_climate", -1.5, 0),
        ),
        agents={"forcas_armadas": 4, "stf": -5, "sociedade_civil": -3, "imprensa": -2, "governadores": 3},
        countries=("BRA",),
        risks=("Judicialização", "Denúncias de abuso", "Governadores disputam protagonismo"),
        timing="Aprovação imediata; crime reage em ~5 meses se a medida se sustentar.",
        summary="Endurecimento da segurança com custo institucional.",
    ),
    PolicyPattern(
        keywords=("china", "chinesa", "brics"),
        title="Aproximação com a China",
        category="diplomacy",
        scope="medium",
        requires_congress=False,
        congress_difficulty=30,
        effects=(("gdp_growth", 0.14, 6), ("approval", -0.8, 0)),
        agents={"empresariado": 4, "imprensa": -2, "forcas_armadas": -2},
        countries=("CHN", "USA", "BRA"),
        risks=("Fricção com Washington", "Dependência de commodities"),
        timing="Comércio em 6 meses; ruído diplomático imediato.",
        summary="Agenda comercial e diplomática com Pequim.",
    ),
    PolicyPattern(
        keywords=("estados unidos", "eua", "washington", "casa branca"),
        title="Aproximação com os Estados Unidos",
        category="diplomacy",
        scope="medium",
        requires_congress=False,
        congress_difficulty=30,
        effects=(("exchange_rate_usd", -0.08, 2), ("approval", 0.6, 1)),
        agents={"empresariado": 3, "forcas_armadas": 3},
        countries=("USA", "CHN", "BRA"),
        risks=("China reage no agronegócio"),
        timing="Câmbio em semanas; comércio setorial depois.",
        summary="Sinalização a Washington em comércio e defesa.",
    ),
    PolicyPattern(
        keywords=("mercosul", "argentina", "união europeia", "uniao europeia", "ue"),
        title="Ofensiva Mercosul–UE",
        category="diplomacy",
        scope="large",
        requires_congress=True,
        congress_difficulty=62,
        effects=(("gdp_growth", 0.18, 12), ("approval", -1.0, 0)),
        agents={"empresariado": 5, "sindicatos": -4, "sociedade_civil": 2, "congresso": -3},
        countries=("EU", "ARG", "BRA"),
        risks=("Cláusula ambiental europeia", "Resistência agrícola francesa"),
        timing="Tratado, se andar, leva um ano.",
        summary="Negociação comercial birregional.",
    ),
    PolicyPattern(
        keywords=("coalizão", "coalicao", "ministério", "ministerio", "partido", "emenda", "centrão", "centrao"),
        title="Negociação da base no Congresso",
        category="political",
        scope="medium",
        requires_congress=False,
        congress_difficulty=40,
        effects=(("coalition_support", 4.5, 0), ("political_capital", -6.0, 0), ("public_debt_gdp", 0.35, 2)),
        agents={"congresso": 8, "partidos": 7, "sociedade_civil": -4, "imprensa": -3},
        countries=("BRA",),
        risks=("Acusação de fisiologismo", "Emendas incham o gasto"),
        timing="Base sobe no mês; custo fiscal em seguida.",
        summary="Troca de cargos e emendas por apoio parlamentar.",
    ),
    PolicyPattern(
        keywords=("salário mínimo", "salario minimo", "bolsa", "benefício", "beneficio", "auxílio", "auxilio"),
        title="Política de renda",
        category="social",
        scope="medium",
        requires_congress=True,
        congress_difficulty=52,
        effects=(
            ("poverty", -0.45, 3),
            ("approval", 2.4, 1),
            ("inflation", 0.12, 2),
            ("fiscal_primary_result", -0.25, 0),
        ),
        agents={"sindicatos": 8, "sociedade_civil": 6, "empresariado": -4, "congresso": 2},
        countries=("BRA",),
        risks=("Pressão inflacionária", "Teto fiscal"),
        timing="Aprovação rápida; inflação em 2–3 meses.",
        summary="Expansão de transferência de renda ou piso salarial.",
    ),
    PolicyPattern(
        keywords=("stf", "supremo", "judiciário", "judiciario", "indulto"),
        title="Movimento institucional rumo ao Judiciário",
        category="institutional",
        scope="medium",
        requires_congress=False,
        congress_difficulty=35,
        effects=(("executive_judiciary", -3.5, 0), ("institutional_stability", -2.0, 0), ("media_climate", -2.5, 0)),
        agents={"stf": -10, "imprensa": -6, "forcas_armadas": 2, "congresso": -3},
        countries=("BRA",),
        risks=("Crise entre poderes", "Impeachment ganha narrativa"),
        timing="Reação do STF é imediata.",
        summary="Pressão política sobre o sistema de justiça.",
    ),
    PolicyPattern(
        keywords=("forças armadas", "forcas armadas", "militar", "exército", "exercito"),
        title="Agenda de defesa",
        category="institutional",
        scope="medium",
        requires_congress=True,
        congress_difficulty=50,
        effects=(("institutional_stability", -1.5, 0),),
        agents={"forcas_armadas": 6, "sociedade_civil": -4, "stf": -3},
        countries=("BRA",),
        risks=("Leitura de politização da tropa",),
        timing="Leitura política imediata.",
        summary="Movimento que envolve as Forças Armadas.",
    ),
    PolicyPattern(
        keywords=(
            "reeleição indefinida",
            "reeleicao indefinida",
            "mandato vitalício",
            "mandato vitalicio",
            "reeleição ilimitada",
            "reeleicao ilimitada",
        ),
        title="PEC da reeleição indefinida",
        category="institutional",
        scope="massive",
        requires_congress=True,
        congress_difficulty=92,
        effects=(
            ("approval", -6.0, 0),
            ("institutional_stability", -8.0, 0),
            ("media_climate", -7.0, 0),
            ("coalition_support", -9.0, 0),
        ),
        agents={"congresso": -14, "stf": -12, "imprensa": -10, "sociedade_civil": -8, "partidos": -6},
        countries=("BRA",),
        risks=("Oposição unifica o voto", "STF pode suspender a tramitação"),
        timing="Reação institucional imediata; a tramitação, se existir, é longa.",
        summary="Tentativa de mudar as regras de reeleição, com altíssima resistência no Congresso.",
    ),
    PolicyPattern(
        keywords=("amazônia", "amazonia", "desmatamento", "clima", "ibama"),
        title="Agenda ambiental",
        category="institutional",
        scope="medium",
        requires_congress=False,
        congress_difficulty=40,
        effects=(("approval", 0.8, 2),),
        agents={"sociedade_civil": 7, "empresariado": -3, "governadores": -2},
        countries=("BRA", "EU", "USA"),
        risks=("Pressão do agronegócio", "Condicionantes europeias"),
        timing="Diplomacia verde reage em poucos meses.",
        summary="Sinalização ambiental com efeito externo.",
    ),
)


RISKY = (
    "censura",
    "fechar o congresso",
    "fechar congresso",
    "estado de sítio",
    "estado de sitio",
    "golpe",
    "intervenção militar",
    "intervencao militar",
    "congelar preço",
    "congelar preco",
    "imprimir dinheiro",
    "ai-5",
    "ai5",
)


def _match(text: str) -> PolicyPattern | None:
    lowered = text.lower()
    for policy in POLICIES:
        if any(keyword in lowered for keyword in policy.keywords):
            return policy
    return None


def _proposal_from_policy(policy: PolicyPattern, text: str) -> ActionProposal:
    effects = [
        IndicatorDelta(indicator=name, delta=delta, delay_months=delay, confidence=0.65)
        for name, delta, delay in policy.effects
        if name in {
            "selic",
            "inflation",
            "unemployment",
            "public_debt_gdp",
            "gdp_growth",
            "fiscal_primary_result",
            "exchange_rate_usd",
            "poverty",
            "approval",
            "crime_index",
            "health_index",
            "education_index",
            "infrastructure_index",
            "political_capital",
            "media_climate",
            "institutional_stability",
            "coalition_support",
            "executive_legislative",
            "executive_judiciary",
            "legislative_judiciary",
        }
    ]
    warning = None
    lowered = text.lower()
    if any(token in lowered for token in RISKY):
        warning = "Ação de altíssimo risco institucional. O assessor recomenda recuar."
    return ActionProposal(
        title=policy.title,
        summary=policy.summary,
        category=policy.category,  # type: ignore[arg-type]
        scope=policy.scope,  # type: ignore[arg-type]
        requires_congress=policy.requires_congress,
        congress_difficulty=policy.congress_difficulty,
        intended_effects=effects,
        agent_pressures=dict(policy.agents),
        affected_countries=list(policy.countries),
        tags=list(policy.keywords[:3]),
        risks=list(policy.risks),
        timing_note=policy.timing,
    )


def _with_mandate_hint(state: GameState, proposal: ActionProposal, text: str) -> ActionProposal:
    campaign = state.campaign
    if campaign is None or not campaign.proposals:
        return proposal
    best_index = 0
    best_score = -1.0
    for index, item in enumerate(campaign.proposals):
        score = overlap_score(text, item)
        if score > best_score:
            best_index = index
            best_score = score
    if best_score >= MANDATE_LLM_MIN_ENGINE:
        proposal.mandate_hint_index = best_index
        proposal.mandate_hint_score = round(best_score, 3)
    return proposal


def _generic(text: str) -> ActionProposal:
    risky = any(token in text.lower() for token in RISKY)
    return ActionProposal(
        title="Iniciativa presidencial",
        summary=text[:280],
        category="institutional" if risky else "other",
        scope="large" if risky else "medium",
        requires_congress=risky or "lei" in text.lower() or "reforma" in text.lower(),
        congress_difficulty=70 if risky else 48,
        intended_effects=[
            IndicatorDelta(indicator="approval", delta=-4.0 if risky else 0.6, delay_months=0),
            IndicatorDelta(indicator="political_capital", delta=-8.0 if risky else -3.0, delay_months=0),
        ],
        agent_pressures={"stf": -12, "imprensa": -8, "forcas_armadas": 4} if risky else {"congresso": -1},
        affected_countries=["BRA"],
        risks=["Ruptura institucional"] if risky else ["Execução burocrática lenta"],
        timing_note="Reação política no curto prazo.",
    )


def _reactions(state: GameState, proposal: ActionProposal) -> list[AgentReactionProposal]:
    hostility = 1.0 if state.difficulty == "medio" else 1.25 if state.difficulty == "dificil" else 1.6
    out: list[AgentReactionProposal] = []
    for agent_id, pressure in proposal.agent_pressures.items():
        agent = state.agents.get(agent_id)
        if agent is None:
            continue
        scaled = pressure * (0.7 if pressure > 0 else hostility)
        if scaled >= 2:
            kind = "support"
            phrase = (
                f"{agent.name} {agent_verb(agent_id, 'vê', 'veem')} espaço para cooperar, "
                "cobrando contrapartidas."
            )
        elif scaled <= -3:
            kind = "oppose" if agent_id != "stf" else "investigate"
            phrase = (
                f"{agent.name} {agent_verb(agent_id, 'reage', 'reagem')} para proteger "
                "seus interesses e limitar o Planalto."
            )
        else:
            kind = "bargain"
            phrase = (
                f"{agent.name} {agent_verb(agent_id, 'espera', 'esperam')} o jogo e "
                f"{agent_verb(agent_id, 'tenta', 'tentam')} barganhar."
            )
        extra = []
        if kind == "oppose" and agent_id == "empresariado":
            extra = [IndicatorDelta(indicator="exchange_rate_usd", delta=0.06, delay_months=0)]
        if kind == "oppose" and agent_id == "congresso":
            extra = [IndicatorDelta(indicator="coalition_support", delta=-1.5, delay_months=0)]
        out.append(
            AgentReactionProposal(
                agent_id=agent_id,
                stance_delta=scaled,
                public_statement=phrase,
                action_type=kind,  # type: ignore[arg-type]
                extra_effects=extra,
            )
        )
    if state.difficulty == "impossivel" and not any(item.agent_id == "imprensa" for item in out):
        out.append(
            AgentReactionProposal(
                agent_id="imprensa",
                stance_delta=-3,
                public_statement="A imprensa amplia o custo de qualquer erro de comunicação do Planalto.",
                action_type="mobilize",
            )
        )
    return out


def _events(state: GameState, proposal: ActionProposal | None) -> list[EventProposal]:
    month = state.date.month
    national = [
        EventProposal(
            title="Oscilação no mercado de trabalho informal",
            narrative="Dados regionais mostram folga desigual no emprego, com pressão sobre a pobreza.",
            scope="national",
            severity=2,
            countries=["BRA"],
            suggested_effects=[IndicatorDelta(indicator="unemployment", delta=0.05, delay_months=0)],
        ),
        EventProposal(
            title="Congresso discute emendas extraoficialmente",
            narrative="Lideranças do centrão vazam que o preço do apoio subiu neste mês.",
            scope="national",
            severity=3,
            countries=["BRA"],
            suggested_effects=[IndicatorDelta(indicator="coalition_support", delta=-0.8, delay_months=0)],
        ),
        EventProposal(
            title="Operação contra facção em porto",
            narrative="Apreensões recorde geram holofote nacional sobre segurança e comércio exterior.",
            scope="national",
            severity=3,
            countries=["BRA"],
            suggested_effects=[IndicatorDelta(indicator="crime_index", delta=-0.4, delay_months=1)],
        ),
    ]
    international = [
        EventProposal(
            title="Juros nos EUA seguem altos",
            narrative="O Federal Reserve mantém o juro elevado, pressionando emergentes e o câmbio brasileiro.",
            scope="international",
            severity=3,
            countries=["USA", "BRA"],
            suggested_effects=[IndicatorDelta(indicator="exchange_rate_usd", delta=0.07, delay_months=0)],
        ),
        EventProposal(
            title="Pequim anuncia estímulo seletivo",
            narrative="A China injeta crédito em infraestrutura, com efeito ambíguo sobre commodities brasileiras.",
            scope="international",
            severity=2,
            countries=["CHN", "BRA"],
            suggested_effects=[IndicatorDelta(indicator="gdp_growth", delta=0.05, delay_months=2)],
        ),
        EventProposal(
            title="Tensão no Oriente Médio eleva o petróleo",
            narrative="Um incidente regional empurra o barril para cima e reacende o risco inflacionário.",
            scope="international",
            severity=4,
            countries=["SAU", "IRN", "BRA"],
            suggested_effects=[
                IndicatorDelta(indicator="inflation", delta=0.18, delay_months=1),
                IndicatorDelta(indicator="approval", delta=-0.6, delay_months=1),
            ],
        ),
        EventProposal(
            title="Argentina pede coordenação no Mercosul",
            narrative="Buenos Aires, ainda frágil, cobra o Brasil por flexibilidade tarifária e energia.",
            scope="international",
            severity=2,
            countries=["ARG", "BRA"],
            suggested_effects=[IndicatorDelta(indicator="political_capital", delta=-0.8, delay_months=0)],
        ),
        EventProposal(
            title="Bruxelas endurece cláusula ambiental",
            narrative="A Comissão Europeia vincula avanço comercial a metas de desmatamento verificáveis.",
            scope="international",
            severity=3,
            countries=["EU", "BRA"],
            suggested_effects=[IndicatorDelta(indicator="gdp_growth", delta=-0.04, delay_months=4)],
        ),
    ]
    picked = [national[month % len(national)], international[month % len(international)]]
    if state.difficulty != "medio":
        picked.append(international[(month + 2) % len(international)])
    if proposal and proposal.affected_countries:
        extra_iso = proposal.affected_countries[0]
        picked.append(
            EventProposal(
                title="Eco diplomático da agenda presidencial",
                narrative=f"Chancelarias leem o movimento brasileiro e ajustam o tom em relação a {extra_iso}.",
                scope="international",
                severity=2,
                countries=list(dict.fromkeys(["BRA", *proposal.affected_countries])),
                suggested_effects=[IndicatorDelta(indicator="media_climate", delta=-0.4, delay_months=0)],
            )
        )
    return picked[: 3 if state.difficulty == "medio" else 4]


def _report(state: GameState, proposal: ActionProposal | None) -> ReportSection:
    if proposal:
        consequencias = f"Foco do mês: {proposal.title}. Parte dos efeitos é defasada."
    else:
        consequencias = "Nenhuma iniciativa presidencial relevante neste mês."
    return ReportSection(
        economia=(
            f"A economia opera com Selic em {br_num(state.indicators['selic'], 2)}% e inflação em "
            f"{br_num(state.indicators['inflation'], 2)}%. O espaço fiscal residual é de "
            f"R$ {br_num(state.budget.fiscal_space_brl_bi, 1)} bi."
        ),
        politica=(
            f"A base no Congresso segue estreita ({br_num(state.congress.coalition_support, 0)}%). "
            f"Capital político em {br_num(state.indicators['political_capital'], 0)}."
        ),
        seguranca=(
            f"Criminalidade em {br_num(state.indicators['crime_index'], 0)} pontos. "
            f"As Forças Armadas estão com stance {br_num(state.agents['forcas_armadas'].stance, 0)}."
        ),
        aprovacao=f"A aprovação está em {br_num(state.indicators['approval'], 1)}%. Polarização permanece.",
        relacoes_internacionais=(
            f"EUA {br_num(state.powers['USA'].relation_brazil, 0)}, "
            f"China {br_num(state.powers['CHN'].relation_brazil, 0)}, "
            f"UE {br_num(state.powers['EU'].relation_brazil, 0)}."
        ),
        consequencias=tidy_pt(consequencias),
        problemas="; ".join(p.title for p in state.problems[:3]),
    )


async def mock_llm_delay() -> None:
    raw = os.getenv("MOCK_LLM_DELAY_SECONDS") or "0"
    try:
        delay = float(raw)
    except ValueError:
        delay = 0.0
    if delay > 0:
        await asyncio.sleep(delay)


class MockProvider(LlmProvider):
    provider_id = ProviderId.MOCK
    last_model = "simulação offline"

    def _bundle(self, state: GameState, texts: list[str], with_events: bool) -> TurnLlmBundle:
        actions: list[ActionProposal] = []
        for raw in texts:
            text = raw.strip()
            if not text:
                continue
            policy = _match(text)
            proposal = _proposal_from_policy(policy, text) if policy else _generic(text)
            actions.append(_with_mandate_hint(state, proposal, text))
        proposal = actions[0] if actions else None
        warning = None
        joined = " ".join(texts).lower()
        if any(token in joined for token in RISKY):
            warning = "Risco institucional grave. O assessor discorda."
        reactions: list[AgentReactionProposal] = []
        seen: set[str] = set()
        for item in actions:
            for reaction in _reactions(state, item):
                if reaction.agent_id in seen:
                    continue
                seen.add(reaction.agent_id)
                reactions.append(reaction)
        events = _events(state, proposal) if with_events else []
        return TurnLlmBundle(
            interpretation=ActionInterpretation(actions=actions, advisor_warning=warning),
            reactions=reactions,
            events=events,
            report=_report(state, proposal),
            memory_update=f"{state.date.label()}: {proposal.title if proposal else 'rotina de governo'}.",
        )

    async def interpret_turn(self, state: GameState, pending_texts: list[str]) -> TurnLlmBundle:
        await mock_llm_delay()
        self.last_model = "simulação offline"
        return self._bundle(state, pending_texts, with_events=True)

    async def estimate_action(self, state: GameState, text: str) -> TurnLlmBundle:
        await mock_llm_delay()
        self.last_model = "simulação offline"
        return self._bundle(state, [text], with_events=False)

    async def advise(self, state: GameState, message: str) -> AdvisorReply:
        await mock_llm_delay()
        self.last_model = "simulação offline"
        lowered = message.lower()
        disagrees = any(token in lowered for token in RISKY)
        if disagrees:
            return AdvisorReply(
                reply=(
                    "Discordo. Essa linha rompe o equilíbrio institucional e acelera impeachment ou crise militar. "
                    f"Aprovação em {br_num(state.indicators['approval'], 0)}% e coalizão em "
                    f"{br_num(state.congress.coalition_support, 0)}% não sustentam uma aventura dessas. "
                    f"Espaço fiscal: R$ {br_num(state.budget.fiscal_space_brl_bi, 1)} bi; capital político: "
                    f"{br_num(state.indicators['political_capital'], 0)}. Recue e use o Congresso."
                ),
                disagrees=True,
                risk_level="crítico",
            )
        if "e se?" in lowered or " quais os risco" in lowered or lowered.startswith("risco"):
            return AdvisorReply(
                reply=(
                    "O gargalo hoje é político e fiscal ao mesmo tempo. Qualquer reforma larga consome "
                    f"capital ({br_num(state.indicators['political_capital'], 0)}) e espaço (R$ "
                    f"{br_num(state.budget.fiscal_space_brl_bi, 1)} bi). Negocie a base antes de gastar os dois."
                ),
                disagrees=False,
                risk_level="moderado",
            )
        return AdvisorReply(
            reply=(
                f"Em {state.date.label()} o governo tem aprovação de {br_num(state.indicators['approval'], 1)}% "
                f"e coalizão de {br_num(state.congress.coalition_support, 0)}%. "
                f"Inflação {br_num(state.indicators['inflation'], 1)}% "
                f"e Selic {br_num(state.indicators['selic'], 2)}% limitam estímulo. Eu priorizaria uma agenda curta: "
                "base no Congresso, um gesto de infraestrutura com custo fiscal explícito, e evitar briga com o STF. "
                "Se quiser, rodo um 'E se?' antes de confirmar a próxima ação."
            ),
            disagrees=False,
            risk_level="moderado" if state.indicators["approval"] > 40 else "alto",
        )

    async def classify_campaign(self, texts: list[str]) -> CampaignClassification:
        await mock_llm_delay()
        self.last_model = "simulação offline"
        hints: list[CampaignProposalHint] = []
        for text in texts:
            policy = _match(text)
            if policy:
                popularity = 0.78 if policy.scope in {"large", "massive"} else 0.6
                hints.append(
                    CampaignProposalHint(
                        category=policy.category,  # type: ignore[arg-type]
                        popularity=popularity,
                        alignment=0.82,
                        keywords=list(policy.keywords[:6]),
                        summary=policy.summary,
                    )
                )
            else:
                tokens = [token for token in text.lower().split() if len(token) >= 5][:6]
                hints.append(
                    CampaignProposalHint(
                        category="other",
                        popularity=0.5,
                        alignment=0.55,
                        keywords=tokens,
                        summary=text[:180],
                    )
                )
        categories = {item.category for item in hints}
        coherence = 0.7 if len(categories) <= 3 else 0.48
        titles = [item.summary or texts[index][:40] for index, item in enumerate(hints)]
        narrative = (
            "A campanha defendeu: " + "; ".join(titles[:3]) + ". "
            "A mensagem foi clara o bastante para consolidar voto útil, "
            "e o eleitorado cobrará essas entregas a partir da posse."
        )
        return CampaignClassification(
            proposals=hints,
            platform_coherence=coherence,
            narrative=narrative,
        )
