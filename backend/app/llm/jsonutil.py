from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError


class JsonParseError(ValueError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise JsonParseError("A resposta da IA não contém um objeto JSON.")
    blob = cleaned[start : end + 1]
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        repaired = blob.replace("\r", " ")
        repaired = re.sub(r",\s*}", "}", repaired)
        repaired = re.sub(r",\s*]", "]", repaired)
        try:
            data = json.loads(repaired)
        except json.JSONDecodeError as exc:
            raise JsonParseError("JSON inválido na resposta da IA.") from exc
    if not isinstance(data, dict):
        raise JsonParseError("O JSON da IA precisa ser um objeto.")
    return data


def parse_model(text: str, model: type[BaseModel]) -> BaseModel:
    data = extract_json_object(text)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise JsonParseError(str(exc)) from exc
