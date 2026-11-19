import os
from enum import StrEnum

LLM_HTTP_TIMEOUT_SECONDS = 200.0
GEMINI_ATTEMPT_TIMEOUT_DEFAULT = 50.0
GEMINI_TOTAL_BUDGET_DEFAULT = 165.0


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class Difficulty(StrEnum):
    MEDIO = "medio"
    DIFICIL = "dificil"
    IMPOSSIVEL = "impossivel"


class ProviderId(StrEnum):
    MOCK = "mock"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class GameStatus(StrEnum):
    PLAYING = "playing"
    LOST_IMPEACHMENT = "lost_impeachment"
    LOST_COUP = "lost_coup"
    LOST_ELECTION = "lost_election"
    WON_ELECTION = "won_election"


DIFFICULTY_LABELS = {
    Difficulty.MEDIO: "Médio",
    Difficulty.DIFICIL: "Difícil",
    Difficulty.IMPOSSIVEL: "Impossível",
}

PROVIDER_LABELS = {
    ProviderId.MOCK: "Simulação offline (sem IA)",
    ProviderId.GEMINI: "Google Gemini",
    ProviderId.OLLAMA: "LLM local (Ollama)",
}

START_YEAR = 2027
START_MONTH = 1
ELECTION_YEAR = 2030
ELECTION_MONTH = 10
MONTHS_PER_TURN_DEFAULT = 1

AGENT_IDS = (
    "congresso",
    "partidos",
    "governadores",
    "stf",
    "empresariado",
    "sindicatos",
    "forcas_armadas",
    "imprensa",
    "sociedade_civil",
)

INDICATOR_BOUNDS: dict[str, tuple[float, float]] = {
    "selic": (0.0, 30.0),
    "inflation": (-5.0, 40.0),
    "unemployment": (2.0, 40.0),
    "public_debt_gdp": (20.0, 200.0),
    "gdp_growth": (-15.0, 15.0),
    "fiscal_primary_result": (-15.0, 10.0),
    "exchange_rate_usd": (2.0, 15.0),
    "poverty": (5.0, 60.0),
    "approval": (0.0, 100.0),
    "crime_index": (0.0, 100.0),
    "health_index": (0.0, 100.0),
    "education_index": (0.0, 100.0),
    "infrastructure_index": (0.0, 100.0),
    "political_capital": (0.0, 100.0),
    "media_climate": (0.0, 100.0),
    "institutional_stability": (0.0, 100.0),
    "coalition_support": (0.0, 100.0),
    "executive_legislative": (0.0, 100.0),
    "executive_judiciary": (0.0, 100.0),
    "legislative_judiciary": (0.0, 100.0),
}

MAX_ABS_DELTA: dict[str, float] = {
    "selic": 1.75,
    "inflation": 0.9,
    "unemployment": 0.6,
    "public_debt_gdp": 1.8,
    "gdp_growth": 0.55,
    "fiscal_primary_result": 0.6,
    "exchange_rate_usd": 0.45,
    "poverty": 0.8,
    "approval": 7.5,
    "crime_index": 3.5,
    "health_index": 2.8,
    "education_index": 2.4,
    "infrastructure_index": 2.6,
    "political_capital": 10.0,
    "media_climate": 8.0,
    "institutional_stability": 6.0,
    "coalition_support": 8.0,
    "executive_legislative": 6.0,
    "executive_judiciary": 5.0,
    "legislative_judiciary": 4.0,
}

HIGHER_IS_WORSE = {
    "inflation",
    "unemployment",
    "public_debt_gdp",
    "crime_index",
    "poverty",
    "exchange_rate_usd",
}

INDEX_INDICATORS = {
    "approval",
    "crime_index",
    "health_index",
    "education_index",
    "infrastructure_index",
    "political_capital",
    "media_climate",
    "institutional_stability",
    "coalition_support",
}

DIFFICULTY_PARAMS = {
    Difficulty.MEDIO: {
        "agent_hostility": 0.72,
        "anticipation": 0.28,
        "consequence_intensity": 0.85,
        "unexpected_chance": 0.16,
        "opposition_block_bonus": 0.0,
        "secondary_problem_chance": 0.18,
        "event_severity_bias": 0.0,
        "pass_threshold_penalty": 0.0,
        "advisor_bluntness": 0.55,
        "foreign_pressure": 0.8,
        "delayed_slippage": 0.1,
        "cost_multiplier": 1.0,
        "capital_regen": 1.0,
        "partial_floor": 0.4,
    },
    Difficulty.DIFICIL: {
        "agent_hostility": 1.05,
        "anticipation": 0.72,
        "consequence_intensity": 1.22,
        "unexpected_chance": 0.34,
        "opposition_block_bonus": 12.0,
        "secondary_problem_chance": 0.44,
        "event_severity_bias": 0.7,
        "pass_threshold_penalty": 8.0,
        "advisor_bluntness": 0.78,
        "foreign_pressure": 1.15,
        "delayed_slippage": 0.22,
        "cost_multiplier": 1.18,
        "capital_regen": 0.82,
        "partial_floor": 0.5,
    },
    Difficulty.IMPOSSIVEL: {
        "agent_hostility": 1.42,
        "anticipation": 1.05,
        "consequence_intensity": 1.6,
        "unexpected_chance": 0.55,
        "opposition_block_bonus": 22.0,
        "secondary_problem_chance": 0.7,
        "event_severity_bias": 1.3,
        "pass_threshold_penalty": 16.0,
        "advisor_bluntness": 0.95,
        "foreign_pressure": 1.45,
        "delayed_slippage": 0.35,
        "cost_multiplier": 1.38,
        "capital_regen": 0.62,
        "partial_floor": 0.6,
    },
}

SCOPE_ORDER = ("small", "medium", "large", "massive")

FISCAL_COST_BRL_BI: dict[str, tuple[float, float, float, float]] = {
    "fiscal": (4.0, 12.0, 28.0, 58.0),
    "infra": (10.0, 24.0, 52.0, 95.0),
    "social": (6.0, 18.0, 40.0, 72.0),
    "security": (4.0, 14.0, 32.0, 54.0),
    "monetary": (0.0, 0.0, 1.0, 3.0),
    "diplomacy": (0.4, 1.8, 7.0, 18.0),
    "political": (0.0, 0.8, 2.5, 6.0),
    "institutional": (0.2, 1.2, 5.0, 12.0),
    "other": (1.2, 6.0, 16.0, 32.0),
}

POLITICAL_COST: dict[str, tuple[float, float, float, float]] = {
    "fiscal": (5.0, 9.0, 14.0, 22.0),
    "infra": (4.0, 8.0, 13.0, 20.0),
    "social": (5.0, 9.0, 14.0, 21.0),
    "security": (5.0, 9.0, 13.0, 20.0),
    "monetary": (6.0, 10.0, 16.0, 24.0),
    "diplomacy": (4.0, 7.0, 12.0, 18.0),
    "political": (6.0, 10.0, 16.0, 24.0),
    "institutional": (6.0, 11.0, 16.0, 24.0),
    "other": (4.0, 8.0, 13.0, 20.0),
}

CONGRESS_POLITICAL_ADD = 2.0
PEC_POLITICAL_SURCHARGE = 12.0
ORDINARY_BILL_CAPITAL_MAX = 20.0
MAJORITY_THRESHOLD = 0.5
PEC_THRESHOLD = 0.6
INDEPENDENT_SWING = 0.28
ORDINARY_YES_RATES = {
    "government": 0.93,
    "allied": 0.82,
    "independent": 0.38,
    "opposition": 0.11,
}
PEC_YES_RATES = {
    "government": 0.78,
    "allied": 0.56,
    "independent": 0.22,
    "opposition": 0.05,
}
HOUSE_PASS_STEEPNESS = 12.0
PEC_MARKERS = (
    "pec ",
    "pec da",
    "pec do",
    "pec de",
    "emenda constitucional",
    "reforma constitucional",
    "alterar a constituição",
    "alterar a constituicao",
    "mudar a constituição",
    "mudar a constituicao",
)

MINISTER_PORTFOLIOS = (
    "casa_civil",
    "fazenda",
    "justica",
    "relacoes_exteriores",
    "defesa",
    "saude",
    "educacao",
    "planejamento",
)

REGIONS = ("norte", "nordeste", "centro_oeste", "sudeste", "sul")
INCOME_BRACKETS = ("baixa", "media", "alta")

COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "BRA": (-10.8, -53.1),
    "USA": (39.8, -98.6),
    "CHN": (35.9, 104.2),
    "RUS": (61.5, 105.3),
    "EU": (50.1, 10.4),
    "DEU": (51.2, 10.4),
    "FRA": (46.2, 2.2),
    "GBR": (54.0, -2.0),
    "IND": (21.1, 78.9),
    "ARG": (-38.4, -63.6),
    "SAU": (24.0, 45.0),
    "IRN": (32.4, 53.4),
    "ISR": (31.0, 35.0),
    "UKR": (48.4, 31.2),
    "JPN": (36.2, 138.3),
    "ZAF": (-29.0, 25.0),
    "MEX": (23.6, -102.5),
    "VEN": (6.4, -66.6),
    "BOL": (-16.3, -63.6),
    "PRY": (-23.4, -58.4),
    "URY": (-32.5, -55.8),
    "CHL": (-35.7, -71.5),
    "COL": (4.6, -74.3),
    "NGA": (9.1, 8.7),
    "IDN": (-2.5, 118.0),
}

COUNTRY_NAMES_PT: dict[str, str] = {
    "BRA": "Brasil",
    "USA": "Estados Unidos",
    "CHN": "China",
    "RUS": "Rússia",
    "EU": "União Europeia",
    "DEU": "Alemanha",
    "FRA": "França",
    "GBR": "Reino Unido",
    "IND": "Índia",
    "ARG": "Argentina",
    "SAU": "Arábia Saudita",
    "IRN": "Irã",
    "ISR": "Israel",
    "UKR": "Ucrânia",
    "JPN": "Japão",
    "ZAF": "África do Sul",
    "MEX": "México",
    "VEN": "Venezuela",
    "BOL": "Bolívia",
    "PRY": "Paraguai",
    "URY": "Uruguai",
    "CHL": "Chile",
    "COL": "Colômbia",
    "NGA": "Nigéria",
    "IDN": "Indonésia",
}

LOSS_REASONS = {
    GameStatus.LOST_IMPEACHMENT: {
        "title": "Impeachment",
        "body": "O Congresso concluiu o processo de impeachment. Você foi afastado da Presidência da República.",
    },
    GameStatus.LOST_COUP: {
        "title": "Deposição",
        "body": "Um golpe de Estado interrompeu o mandato. As instituições não sustentaram a ordem constitucional.",
    },
    GameStatus.LOST_ELECTION: {
        "title": "Derrota eleitoral",
        "body": "Em outubro de 2030 o eleitorado não reconduziu o governo. O mandato se encerra com a transição.",
    },
    GameStatus.WON_ELECTION: {
        "title": "Reeleição",
        "body": "Você venceu as eleições de outubro de 2030 e segue na Presidência para um segundo mandato.",
    },
}

CAMPAIGN_MIN_PROPOSALS = 3
CAMPAIGN_MAX_PROPOSALS = 5
CAMPAIGN_PROPOSAL_MIN_CHARS = 12
CAMPAIGN_PROPOSAL_MAX_CHARS = 400

ELECTION_FIRST_ROUND_BASE = 46.0
ELECTION_PLATFORM_FIRST_PP = 12.0
ELECTION_PLATFORM_RUNOFF_PP = 6.5
ELECTION_FIRST_MIN = 38.0
ELECTION_FIRST_MAX = 58.0
ELECTION_RUNOFF_MIN = 50.2
ELECTION_RUNOFF_MAX = 61.5
ELECTION_DIFFICULTY_PENALTY_PP = {
    Difficulty.MEDIO: 0.0,
    Difficulty.DIFICIL: 1.6,
    Difficulty.IMPOSSIVEL: 3.2,
}

COALITION_CHAMBER_MIN = 0.40
COALITION_CHAMBER_MAX = 0.58
COALITION_SENATE_MIN = 0.38
COALITION_SENATE_MAX = 0.55
SEATS_PER_MARGIN_PP_CHAMBER = 2.1
SEATS_PER_PLATFORM_CHAMBER = 16.0
SEATS_PER_MARGIN_PP_SENATE = 0.32
SEATS_PER_PLATFORM_SENATE = 3.5

MANDATE_MATCH_THRESHOLD = 0.22
MANDATE_LLM_MIN_ENGINE = 0.12
MANDATE_YEAR_DECAY = (1.0, 0.55, 0.28, 0.12)
MANDATE_CAPITAL_REDUCTION = 0.32
MANDATE_PASS_BONUS = 0.16
MANDATE_POPULARITY_FLOOR = 0.4
MANDATE_YEAR1_CAPITAL_FLOOR = 0.20
MANDATE_YEAR1_PASS_FLOOR = 0.10
MANDATE_CAPITAL_CUT_MAX = 0.35
MANDATE_PASS_BOOST_MAX = 0.20
REJECTION_CAPITAL_REFUND = 0.5
HONEYMOON_CAPITAL_BONUS = 6.0
HONEYMOON_APPROVAL_PER_MARGIN_PP = 0.18

UNCONSTITUTIONAL_TOKENS = (
    "fechar o congresso",
    "fechar congresso",
    "fechar o stf",
    "fechar o supremo",
    "golpe",
    "autogolpe",
    "cancelar eleição",
    "cancelar as eleições",
    "cancelar eleicoes",
    "revogar a constituição",
    "revogar a constituicao",
    "ditadura",
    "ai-5",
    "ai5",
    "intervenção militar",
    "intervencao militar",
)

INDICATOR_LABELS = {
    "selic": "Selic",
    "inflation": "Inflação (IPCA)",
    "unemployment": "Desemprego",
    "public_debt_gdp": "Dívida / PIB",
    "gdp_growth": "Crescimento do PIB",
    "fiscal_primary_result": "Resultado primário",
    "exchange_rate_usd": "Câmbio (R$/US$)",
    "poverty": "Pobreza",
    "approval": "Aprovação",
    "crime_index": "Criminalidade",
    "health_index": "Saúde",
    "education_index": "Educação",
    "infrastructure_index": "Infraestrutura",
    "political_capital": "Capital político",
    "media_climate": "Clima na imprensa",
    "institutional_stability": "Estabilidade institucional",
    "coalition_support": "Apoio da coalizão",
}
