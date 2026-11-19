export type View = "title" | "new" | "load" | "campaign" | "game" | "settings";

export interface ProviderInfo {
  id: string;
  label: string;
  status: { ok: boolean; message?: string; model?: string; models?: string[] };
}

export interface DifficultyInfo {
  id: string;
  label: string;
  blurb: string;
}

export interface MetaResponse {
  providers: ProviderInfo[];
  difficulties: DifficultyInfo[];
  settings: {
    gemini_api_key_set: boolean;
    gemini_model: string;
    gemini_fallback_models?: string;
    ollama_base_url: string;
    ollama_model: string;
    default_provider: string;
  };
}

export interface Indicator {
  id: string;
  label: string;
  value: number;
}

export interface Agent {
  id: string;
  name: string;
  interests: string[];
  influence: number;
  resources: number;
  stance: number;
}

export interface MapCountry {
  iso: string;
  name: string;
  lat: number;
  lng: number;
  highlight: boolean;
  relation: number | null;
}

export interface HistoryEntry {
  id: string;
  month_index: number;
  date_label: string;
  kind: string;
  title: string;
  body: string;
  countries: string[];
}

export interface Report {
  economia: string;
  politica: string;
  seguranca: string;
  aprovacao: string;
  relacoes_internacionais: string;
  consequencias: string;
  problemas: string;
}

export interface ChatMessage {
  role: "user" | "advisor";
  content: string;
  disagrees: boolean;
  answered_by?: string;
}

export interface ResolvedAction {
  title: string;
  summary: string;
  passed: boolean;
  reason: string;
  category: string;
  execution: "full" | "partial" | "blocked" | "rejected";
  scale: number;
  fiscal_cost_brl_bi: number;
  political_cost: number;
  mandate_applied?: boolean;
  mandate_note?: string;
  capital_refunded?: number;
  limit_kind?: string;
}

export interface EffectPreview {
  indicator: string;
  label: string;
  immediate_delta: number;
  delayed_delta: number;
  delay_months: number;
}

export interface AgentPreview {
  agent_id: string;
  name: string;
  action_type: string;
  statement: string;
  stance_delta: number;
}

export interface WhatIfResult {
  title: string;
  summary: string;
  category: string;
  scope: string;
  fiscal_cost_brl_bi: number;
  political_cost: number;
  fiscal_available: number;
  political_available: number;
  execution: "full" | "partial" | "blocked" | "rejected";
  scale: number;
  resource_message: string;
  requires_congress: boolean;
  pass_chance: number;
  likely_effects: EffectPreview[];
  agent_reactions: AgentPreview[];
  risks: string[];
  timing_note: string;
  advisor_commentary: string;
  disagrees: boolean;
  countries: string[];
  answered_by?: string;
  mandate_applied?: boolean;
  mandate_note?: string;
}

export interface CampaignMandateItem {
  id: string;
  text: string;
  category: string;
  weight: number;
  popularity: number;
  alignment: number;
  keywords: string[];
  summary: string;
}

export interface CampaignResult {
  first_round_share: number;
  runoff: boolean;
  second_round_share: number | null;
  winner_share: number;
  opponent_share: number;
  margin_pp: number;
  turnout: number;
  narrative: string;
  proposals: CampaignMandateItem[];
  coalition_support: number;
  chamber: { seats: number; government: number; allied: number; opposition: number; independent: number } | null;
  senate: { seats: number; government: number; allied: number; opposition: number; independent: number } | null;
  platform_strength: number;
}

export interface Game {
  id: string;
  name: string;
  status: string;
  date_label: string;
  difficulty: string;
  difficulty_label: string;
  provider: string;
  provider_label: string;
  indicators: Indicator[];
  indicator_map: Record<string, number>;
  budget: {
    fiscal_space_brl_bi: number;
    fiscal_space_annual_cap_brl_bi: number;
    monthly_replenish_brl_bi: number;
    year_spent_brl_bi: number;
  };
  political_capital: number;
  congress: {
    coalition_support: number;
    chamber: { seats: number; government: number; allied: number; opposition: number; independent: number };
    senate: { seats: number; government: number; allied: number; opposition: number; independent: number };
  };
  branches: Record<string, number>;
  agents: Agent[];
  powers: Array<{ id: string; name: string; iso: string; relation_brazil: number }>;
  problems: Array<{ id: string; title: string; severity: number }>;
  pending_actions: Array<{ id: string; text: string }>;
  last_report: Report | null;
  last_report_date_label?: string | null;
  last_llm_model?: string | null;
  last_resolved: ResolvedAction[];
  advisor_log: ChatMessage[];
  history: HistoryEntry[];
  highlighted_countries: string[];
  map_countries: MapCountry[];
  impeachment_pressure: number;
  coup_risk: number;
  loss_title: string | null;
  loss_body: string | null;
  months_elapsed: number;
  scheduled_count: number;
  headlines: Array<{ id: string; title: string; outlet: string; tone: string }>;
  advisor_reply?: { reply: string; disagrees: boolean; risk_level: string };
  campaign_pending?: boolean;
  campaign?: CampaignResult | null;
}

export interface SaveRow {
  id: string;
  kind: string;
  name: string;
  updated_at: string;
}
