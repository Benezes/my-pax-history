from __future__ import annotations

from app.constants import DIFFICULTY_LABELS, INDICATOR_LABELS
from app.models import GameState

SCHEMA_HINT = """
Responda SOMENTE um JSON válido, sem markdown, com este formato:
{
  "interpretation": {
    "actions": [
      {
        "title": "string",
        "summary": "string",
        "category": "fiscal|monetary|social|security|infra|diplomacy|political|institutional|other",
        "scope": "small|medium|large|massive",
        "requires_congress": false,
        "congress_difficulty": 50,
        "intended_effects": [{"indicator": "approval", "delta": -1.5, "delay_months": 0, "confidence": 0.6}],
        "agent_pressures": {"congresso": -2},
        "affected_countries": ["BRA"],
        "tags": ["exemplo"],
        "risks": ["risco em português"],
        "timing_note": "quando os efeitos aparecem"
      }
    ],
    "advisor_warning": "string ou null"
  },
  "reactions": [
    {
      "agent_id": "congresso",
      "stance_delta": -2,
      "public_statement": "frase em português",
      "action_type": "support|oppose|bargain|mobilize|investigate|neutral",
      "resource_spend": 0,
      "extra_effects": []
    }
  ],
  "events": [
    {
      "title": "string",
      "narrative": "parágrafo em português",
      "scope": "national|international",
      "severity": 3,
      "countries": ["BRA", "USA"],
      "suggested_effects": [{"indicator": "exchange_rate_usd", "delta": 0.1, "delay_months": 0, "confidence": 0.5}],
      "delayed_effects": []
    }
  ],
  "report": {
    "economia": "...",
    "politica": "...",
    "seguranca": "...",
    "aprovacao": "...",
    "relacoes_internacionais": "...",
    "consequencias": "...",
    "problemas": "..."
  },
  "memory_update": "2 a 4 frases resumindo o mês"
}
Indicadores permitidos: selic, inflation, unemployment, public_debt_gdp, gdp_growth,
fiscal_primary_result, exchange_rate_usd, poverty, approval, crime_index, health_index,
education_index, infrastructure_index, political_capital, media_climate,
institutional_stability, coalition_support, executive_legislative, executive_judiciary,
legislative_judiciary.
agent_id permitido: congresso, partidos, governadores, stf, empresariado, sindicatos,
forcas_armadas, imprensa, sociedade_civil.
NUNCA envie valores absolutos de indicadores. Apenas deltas modestos.
O motor calcula custos fiscais e de capital político; você só estima o escopo.
""".strip()


def _compact_state(state: GameState) -> str:
    ind = state.indicators
    lines = [
        f"Data: {state.date.label()}",
        f"Dificuldade: {DIFFICULTY_LABELS[state.difficulty]}",
        f"Aprovação: {ind['approval']:.1f}%",
        f"Selic: {ind['selic']:.2f}% | Inflação: {ind['inflation']:.2f}% | Desemprego: {ind['unemployment']:.1f}%",
        f"PIB: {ind['gdp_growth']:+.2f}% | Dívida/PIB: {ind['public_debt_gdp']:.1f}%",
        f"Espaço fiscal: R$ {state.budget.fiscal_space_brl_bi:.1f} bi | Capital político: {ind['political_capital']:.0f}",
        f"Coalizão: {state.congress.coalition_support:.0f}% | Estabilidade: {ind['institutional_stability']:.0f}",
        f"Impeachment: {state.impeachment_pressure:.0f} | Risco de golpe: {state.coup_risk:.0f} | Escândalos: {state.scandals:.1f}",
    ]
    for agent in state.agents.values():
        lines.append(
            f"Agente {agent.name}: stance {agent.stance:.0f}, influência {agent.influence:.0f}, interesses: {', '.join(agent.interests)}"
        )
    for power in state.powers.values():
        lines.append(
            f"{power.name}: relação {power.relation_brazil:.0f}, estabilidade {power.stability:.0f}, tensões: {', '.join(power.tensions[:2])}"
        )
    recent = state.history[-8:]
    if recent:
        lines.append("Eventos recentes:")
        for entry in recent:
            lines.append(f"- {entry.date_label} [{entry.kind}] {entry.title}: {entry.body[:180]}")
    lines.append("Resumo de memória: " + state.memory_summary[-1200:])
    return "\n".join(lines)


def difficulty_style(state: GameState) -> str:
    if state.difficulty == "medio":
        return (
            "Dificuldade MÉDIA: desafios coerentes, oposição realista, sem conspiração excessiva. "
            "Consequências proporcionais. Antecipação limitada."
        )
    if state.difficulty == "dificil":
        return (
            "Dificuldade DIFÍCIL: explore vulnerabilidades, gere problemas secundários e "
            "antecipe movimentos. Decisões mal desenhadas devem doer."
        )
    return (
        "Dificuldade IMPOSSÍVEL: cada ação presidencial provoca reação calculada de agentes "
        "internos e externos com interesses próprios. Mesmo boas ideias encontram contorno, "
        "sabotagem institucional, pressão internacional ou custos ocultos. Jogue como xadrez."
    )


def turn_prompt(state: GameState, pending_texts: list[str]) -> str:
    actions = pending_texts or ["(nenhuma ação presidencial neste mês; simule o mundo e os agentes)"]
    listed = "\n".join(f"- {text}" for text in actions)
    return f"""Você é o motor narrativo de um simulador da Presidência do Brasil.
Todo texto visível ao jogador deve estar em português brasileiro.
{difficulty_style(state)}
O motor da simulação aplica regras, custos, votos e indicadores. Você NÃO define indicadores absolutos.
Você interpreta ações, propõe reações de agentes, eventos e redige o relatório a partir do estado.

Estado compacto:
{_compact_state(state)}

Ações presidenciais deste mês:
{listed}

{SCHEMA_HINT}
"""


def estimate_prompt(state: GameState, text: str) -> str:
    return f"""Você é o assessor da Presidência. Faça uma estimativa SECA (what-if) da ação abaixo.
Não invente que a ação já ocorreu. Não altere o mundo. Apenas interprete a ação em JSON.
Texto da ação:
{text}

Estado:
{_compact_state(state)}

{SCHEMA_HINT}
Preencha interpretation.actions com UMA ação. reactions com reações prováveis. events vazio.
report pode ficar vazio. memory_update vazio.
advisor_warning: discorde se a ação for temerária.
"""


def advisor_prompt(state: GameState, message: str) -> str:
    labels = ", ".join(f"{k}={INDICATOR_LABELS[k]}" for k in list(INDICATOR_LABELS)[:8])
    return f"""Você é o assessor-chefe da Presidência da República do Brasil.
Fale em português brasileiro, tom direto, técnico, sem bajulação.
Pode e deve discordar de ideias perigosas (censura, rupturas, golpes, congelamento de preços,
uso político das Forças Armadas, irresponsabilidade fiscal).
Use o estado real. Não invente números fora do estado.
Indicadores: {labels}

Estado:
{_compact_state(state)}

Pergunta do presidente:
{message}

Responda SOMENTE JSON:
{{"reply": "texto", "disagrees": false, "risk_level": "baixo|moderado|alto|crítico"}}
"""
