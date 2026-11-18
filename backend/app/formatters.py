from __future__ import annotations

import re
from typing import Any

PLURAL_AGENT_IDS = frozenset({"sindicatos", "governadores", "partidos", "forcas_armadas"})


def br_num(value: float, digits: int = 1, signed: bool = False) -> str:
    rounded = round(float(value), digits)
    text = f"{rounded:.{digits}f}".replace(".", ",")
    if signed and rounded > 0:
        return "+" + text
    return text


def round_floats(value: Any, digits: int = 2) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {key: round_floats(item, digits) for key, item in value.items()}
    if isinstance(value, list):
        return [round_floats(item, digits) for item in value]
    return value


def agent_verb(agent_id: str, singular: str, plural: str) -> str:
    return plural if agent_id in PLURAL_AGENT_IDS else singular


def tidy_pt(text: str) -> str:
    cleaned = re.sub(r"\.{2,}", ".", text.strip())
    return cleaned.rstrip(".") + "." if cleaned else cleaned
