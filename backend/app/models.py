from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.constants import AGENT_IDS, INDICATOR_BOUNDS, Difficulty, GameStatus, ProviderId

ActionCategory = Literal[
    "fiscal",
    "monetary",
    "social",
    "security",
    "infra",
    "diplomacy",
    "political",
    "institutional",
    "other",
]
ActionScope = Literal["small", "medium", "large", "massive"]
ExecutionMode = Literal["full", "partial", "blocked", "rejected"]


class GameDate(BaseModel):
    year: int
    month: int

    def month_index(self) -> int:
        return (self.year - 2027) * 12 + (self.month - 1)

    def label(self) -> str:
        months = (
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        )
        return f"{months[self.month - 1]} de {self.year}"

    def advance(self, months: int = 1) -> GameDate:
        total = self.year * 12 + (self.month - 1) + months
        year, month0 = divmod(total, 12)
        return GameDate(year=year, month=month0 + 1)


class Chamber(BaseModel):
    seats: int
    government: int
    allied: int
    opposition: int
    independent: int


class Party(BaseModel):
    id: str
    name: str
    chamber_seats: int
    senate_seats: int
    stance: float
    bloc: str
    discipline: float = 70.0


class Congress(BaseModel):
    coalition_support: float
    chamber: Chamber
    senate: Chamber
    parties: list[Party] = Field(default_factory=list)
    plebiscite_unlocked: bool = False


class AgentState(BaseModel):
    id: str
    name: str
    interests: list[str] = Field(default_factory=list)
    influence: float
    resources: float
    stance: float

    @field_validator("stance")
    @classmethod
    def clamp_stance(cls, value: float) -> float:
        return max(-100.0, min(100.0, value))


class Problem(BaseModel):
    id: str
    title: str
    severity: float


class PowerState(BaseModel):
    id: str
    name: str
    iso: str
    lat: float
    lng: float
    gdp_growth: float
    inflation: float
    stability: float
    military_posture: float
    relation_brazil: float
    trade_with_brazil_usd_bi: float
    alignment: str = ""
    interests: list[str] = Field(default_factory=list)
    tensions: list[str] = Field(default_factory=list)


class OrgState(BaseModel):
    id: str
    name: str
    relation_brazil: float
    notes: str = ""


class Flashpoint(BaseModel):
    id: str
    title: str
    severity: float
    countries: list[str] = Field(default_factory=list)


class BudgetState(BaseModel):
    annual_revenue_brl_bi: float
    mandatory_share: float
    fiscal_space_brl_bi: float
    fiscal_space_annual_cap_brl_bi: float
    monthly_replenish_brl_bi: float
    year_spent_brl_bi: float = 0.0


class Minister(BaseModel):
    portfolio: str
    title: str
    name: str
    origin: Literal["automatic", "player"] = "automatic"
    loyalty: float = 55.0
    competence: float = 55.0


class ApprovalBreakdown(BaseModel):
    regions: dict[str, float] = Field(default_factory=dict)
    income: dict[str, float] = Field(default_factory=dict)


class Headline(BaseModel):
    id: str
    month_index: int
    outlet: str
    title: str
    tone: Literal["positive", "neutral", "negative"] = "neutral"
    reach: float = 1.0


class IndicatorDelta(BaseModel):
    indicator: str
    delta: float
    delay_months: int = 0
    confidence: float = 0.6

    @field_validator("indicator")
    @classmethod
    def known_indicator(cls, value: str) -> str:
        allowed = set(INDICATOR_BOUNDS) | {
            "coalition_support",
            "executive_legislative",
            "executive_judiciary",
            "legislative_judiciary",
        }
        if value not in allowed:
            raise ValueError(f"unknown indicator: {value}")
        return value

    @field_validator("delay_months")
    @classmethod
    def non_negative_delay(cls, value: int) -> int:
        return max(0, min(36, value))


class ActionProposal(BaseModel):
    title: str
    summary: str
    category: ActionCategory = "other"
    scope: ActionScope = "medium"
    requires_congress: bool = False
    congress_difficulty: int = 50
    intended_effects: list[IndicatorDelta] = Field(default_factory=list)
    agent_pressures: dict[str, float] = Field(default_factory=dict)
    affected_countries: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    timing_note: str = ""
    mandate_hint_index: int | None = None
    mandate_hint_score: float = 0.0
    contradicts_campaign: bool = False


class ActionInterpretation(BaseModel):
    actions: list[ActionProposal] = Field(default_factory=list)
    advisor_warning: str | None = None


class AgentReactionProposal(BaseModel):
    agent_id: str
    stance_delta: float = 0.0
    public_statement: str
    action_type: Literal["support", "oppose", "bargain", "mobilize", "investigate", "neutral"] = (
        "neutral"
    )
    resource_spend: float = 0.0
    extra_effects: list[IndicatorDelta] = Field(default_factory=list)

    @field_validator("agent_id")
    @classmethod
    def known_agent(cls, value: str) -> str:
        if value not in AGENT_IDS:
            raise ValueError(f"unknown agent: {value}")
        return value


class EventProposal(BaseModel):
    title: str
    narrative: str
    scope: Literal["national", "international"] = "national"
    severity: int = 2
    countries: list[str] = Field(default_factory=list)
    suggested_effects: list[IndicatorDelta] = Field(default_factory=list)
    delayed_effects: list[IndicatorDelta] = Field(default_factory=list)


class ReportSection(BaseModel):
    economia: str = ""
    politica: str = ""
    seguranca: str = ""
    aprovacao: str = ""
    relacoes_internacionais: str = ""
    consequencias: str = ""
    problemas: str = ""


class TurnLlmBundle(BaseModel):
    interpretation: ActionInterpretation = Field(default_factory=ActionInterpretation)
    reactions: list[AgentReactionProposal] = Field(default_factory=list)
    events: list[EventProposal] = Field(default_factory=list)
    report: ReportSection = Field(default_factory=ReportSection)
    memory_update: str = ""


class AdvisorReply(BaseModel):
    reply: str
    disagrees: bool = False
    risk_level: Literal["baixo", "moderado", "alto", "crítico"] = "moderado"


class ActionCost(BaseModel):
    fiscal_brl_bi: float
    political: float
    scope: ActionScope
    category: ActionCategory


class ResourceVerdict(BaseModel):
    mode: ExecutionMode
    scale: float
    fiscal_spent: float
    political_spent: float
    message: str


class ScheduledEffect(BaseModel):
    id: str
    fire_month_index: int
    source: str
    description: str
    deltas: dict[str, float] = Field(default_factory=dict)
    unexpected: bool = False
    countries: list[str] = Field(default_factory=list)


class HistoryEntry(BaseModel):
    id: str
    month_index: int
    date_label: str
    kind: Literal[
        "action",
        "action_result",
        "agent",
        "indicator",
        "event",
        "report",
        "system",
        "loss",
        "save",
        "resource",
    ]
    title: str
    body: str
    countries: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["user", "advisor"]
    content: str
    disagrees: bool = False
    at_month_index: int = 0
    answered_by: str = ""


class PendingAction(BaseModel):
    id: str
    text: str


class ResolvedAction(BaseModel):
    title: str
    summary: str
    passed: bool
    reason: str
    category: str
    execution: ExecutionMode = "full"
    scale: float = 1.0
    fiscal_cost_brl_bi: float = 0.0
    political_cost: float = 0.0
    countries: list[str] = Field(default_factory=list)
    mandate_applied: bool = False
    mandate_note: str = ""
    capital_refunded: float = 0.0
    limit_kind: str = ""


class MapCountry(BaseModel):
    iso: str
    name: str
    lat: float
    lng: float
    highlight: bool = False
    relation: float | None = None


class EffectPreview(BaseModel):
    indicator: str
    label: str
    immediate_delta: float
    delayed_delta: float
    delay_months: int


class AgentPreview(BaseModel):
    agent_id: str
    name: str
    action_type: str
    statement: str
    stance_delta: float


class WhatIfResult(BaseModel):
    title: str
    summary: str
    category: str
    scope: str
    fiscal_cost_brl_bi: float
    political_cost: float
    fiscal_available: float
    political_available: float
    execution: ExecutionMode
    scale: float
    resource_message: str
    requires_congress: bool
    pass_chance: float
    likely_effects: list[EffectPreview] = Field(default_factory=list)
    agent_reactions: list[AgentPreview] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    timing_note: str = ""
    advisor_commentary: str = ""
    disagrees: bool = False
    countries: list[str] = Field(default_factory=list)
    answered_by: str = ""
    mandate_applied: bool = False
    mandate_note: str = ""


class CampaignProposalHint(BaseModel):
    category: ActionCategory = "other"
    popularity: float = 0.5
    alignment: float = 0.5
    keywords: list[str] = Field(default_factory=list)
    summary: str = ""


class CampaignClassification(BaseModel):
    proposals: list[CampaignProposalHint] = Field(default_factory=list)
    platform_coherence: float = 0.5
    narrative: str = ""


class CampaignMandateItem(BaseModel):
    id: str
    text: str
    category: str = "other"
    weight: float = 0.0
    popularity: float = 0.5
    alignment: float = 0.5
    keywords: list[str] = Field(default_factory=list)
    summary: str = ""


class CampaignResult(BaseModel):
    first_round_share: float
    runoff: bool
    second_round_share: float | None = None
    winner_share: float
    opponent_share: float
    margin_pp: float
    turnout: float = 79.2
    narrative: str = ""
    proposals: list[CampaignMandateItem] = Field(default_factory=list)
    coalition_support: float = 0.0
    chamber: Chamber | None = None
    senate: Chamber | None = None
    platform_strength: float = 0.0


class GameState(BaseModel):
    id: str
    name: str = "Partida"
    created_at: str
    updated_at: str
    difficulty: Difficulty
    provider: ProviderId
    provider_model: str = ""
    status: GameStatus = GameStatus.PLAYING
    date: GameDate
    seed: int
    indicators: dict[str, float]
    budget: BudgetState
    congress: Congress
    branches: dict[str, float]
    agents: dict[str, AgentState]
    powers: dict[str, PowerState]
    orgs: dict[str, OrgState]
    flashpoints: list[Flashpoint] = Field(default_factory=list)
    diplomacy: dict[str, float] = Field(default_factory=dict)
    trade: dict[str, float] = Field(default_factory=dict)
    problems: list[Problem] = Field(default_factory=list)
    ministers: list[Minister] = Field(default_factory=list)
    cabinet_mode: Literal["automatic", "player"] = "automatic"
    approval_breakdown: ApprovalBreakdown = Field(default_factory=ApprovalBreakdown)
    headlines: list[Headline] = Field(default_factory=list)
    scheduled_effects: list[ScheduledEffect] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    pending_actions: list[PendingAction] = Field(default_factory=list)
    last_report: ReportSection | None = None
    last_llm_model: str = ""
    last_resolved: list[ResolvedAction] = Field(default_factory=list)
    last_what_if: WhatIfResult | None = None
    advisor_log: list[ChatMessage] = Field(default_factory=list)
    memory_summary: str = ""
    brazil_lore: str = ""
    world_lore: str = ""
    highlighted_countries: list[str] = Field(default_factory=lambda: ["BRA"])
    scandals: float = 0.0
    impeachment_pressure: float = 0.0
    coup_risk: float = 0.0
    consecutive_crisis_months: int = 0
    election_vote_share: float | None = None
    loss_title: str | None = None
    loss_body: str | None = None
    months_elapsed: int = 0
    campaign_pending: bool = False
    campaign: CampaignResult | None = None


class NewGameRequest(BaseModel):
    difficulty: Difficulty
    provider: ProviderId
    api_key: str | None = None
    ollama_model: str | None = None
    gemini_model: str | None = None
    name: str | None = None


class QueueActionRequest(BaseModel):
    text: str = Field(min_length=3, max_length=12000)


class AdvanceRequest(BaseModel):
    months: int = Field(default=1, ge=1, le=6)


class AdvisorRequest(BaseModel):
    message: str = Field(min_length=2, max_length=8000)


class WhatIfRequest(BaseModel):
    text: str = Field(min_length=3, max_length=12000)


class CampaignRequest(BaseModel):
    proposals: list[str]


class SaveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class SettingsUpdate(BaseModel):
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    gemini_fallback_models: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    default_provider: str | None = None


class GeminiModelsRequest(BaseModel):
    api_key: str | None = None
