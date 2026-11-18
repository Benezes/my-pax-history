from enum import StrEnum


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
    "fiscal": (5.0, 16.0, 36.0, 70.0),
    "infra": (12.0, 30.0, 65.0, 115.0),
    "social": (8.0, 24.0, 50.0, 88.0),
    "security": (5.0, 16.0, 38.0, 62.0),
    "monetary": (0.0, 0.0, 1.0, 3.0),
    "diplomacy": (0.4, 1.8, 7.0, 18.0),
    "political": (0.0, 0.8, 2.5, 6.0),
    "institutional": (0.2, 1.2, 5.0, 12.0),
    "other": (1.5, 8.0, 20.0, 40.0),
}

POLITICAL_COST: dict[str, tuple[float, float, float, float]] = {
    "fiscal": (8.0, 15.0, 26.0, 38.0),
    "infra": (6.0, 12.0, 20.0, 30.0),
    "social": (7.0, 14.0, 24.0, 34.0),
    "security": (6.0, 13.0, 22.0, 32.0),
    "monetary": (10.0, 18.0, 28.0, 36.0),
    "diplomacy": (5.0, 10.0, 18.0, 28.0),
    "political": (9.0, 16.0, 27.0, 40.0),
    "institutional": (11.0, 20.0, 32.0, 45.0),
    "other": (6.0, 12.0, 20.0, 30.0),
}

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
