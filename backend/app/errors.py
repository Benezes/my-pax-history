from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

FIELD_PT = {
    "text": "texto da ação",
    "message": "texto",
    "name": "nome",
    "api_key": "chave",
    "gemini_model": "modelo Gemini",
    "ollama_model": "modelo Ollama",
    "ollama_base_url": "URL do Ollama",
}


def translate_error(err: dict) -> str:
    typ = err.get("type") or ""
    loc = err.get("loc") or ()
    ctx = err.get("ctx") or {}
    field = str(loc[-1]) if loc else "campo"
    label = FIELD_PT.get(field, "campo")
    if typ == "string_too_long":
        limit = ctx.get("max_length", 0)
        return f"O {label} pode ter no máximo {limit} caracteres."
    if typ == "string_too_short":
        limit = ctx.get("min_length", 1)
        return f"Escreva pelo menos {limit} caracteres no {label}."
    if typ == "missing":
        return f"O {label} é obrigatório."
    if typ == "value_error":
        return "Há um valor inválido. Revise os dados e tente de novo."
    return "Há um erro nos dados enviados. Revise o texto e tente de novo."


async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    parts = [translate_error(dict(item)) for item in exc.errors()]
    detail = " ".join(dict.fromkeys(parts)) if parts else "Há um erro nos dados enviados."
    return JSONResponse(status_code=422, content={"detail": detail})
