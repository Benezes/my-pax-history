from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.constants import AGENT_IDS, COUNTRY_COORDS, COUNTRY_NAMES_PT
from app.models import (
    AgentState,
    ApprovalBreakdown,
    BudgetState,
    Chamber,
    Congress,
    Flashpoint,
    Minister,
    OrgState,
    Party,
    PowerState,
    Problem,
)
from app.paths import BRAZIL_CONFIG, WORLD_CONFIG


class ConfigError(ValueError):
    pass


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text.strip()
    closing = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing = index
            break
    if closing is None:
        raise ConfigError("Front-matter YAML incompleto: use --- no início e no fim do bloco.")
    data = yaml.safe_load("\n".join(lines[1:closing])) or {}
    if not isinstance(data, dict):
        raise ConfigError("O YAML inicial precisa ser um mapa de chaves e valores.")
    return data, "\n".join(lines[closing + 1 :]).strip()


def load_markdown(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        raise ConfigError(f"Arquivo não encontrado: {path}")
    return split_front_matter(path.read_text(encoding="utf-8"))


def _chamber(raw: dict[str, Any]) -> Chamber:
    return Chamber(
        seats=int(raw.get("seats", 0)),
        government=int(raw.get("government", 0)),
        allied=int(raw.get("allied", 0)),
        opposition=int(raw.get("opposition", 0)),
        independent=int(raw.get("independent", 0)),
    )


def parse_brazil(path: Path | None = None) -> dict[str, Any]:
    data, lore = load_markdown(path or BRAZIL_CONFIG)
    try:
        indicators = {str(k): float(v) for k, v in (data.get("indicators") or {}).items()}
        congress_raw = data.get("congress") or {}
        parties = [
            Party(
                id=str(item.get("id")),
                name=str(item.get("name")),
                chamber_seats=int(item.get("chamber_seats", 0)),
                senate_seats=int(item.get("senate_seats", 0)),
                stance=float(item.get("stance", 0)),
                bloc=str(item.get("bloc", "independent")),
                discipline=float(item.get("discipline", 70)),
            )
            for item in (congress_raw.get("parties") or [])
        ]
        congress = Congress(
            coalition_support=float(congress_raw.get("coalition_support", 45)),
            chamber=_chamber(congress_raw.get("chamber") or {}),
            senate=_chamber(congress_raw.get("senate") or {}),
            parties=parties,
            plebiscite_unlocked=bool(congress_raw.get("plebiscite_unlocked", False)),
        )
        budget_raw = data.get("budget") or {}
        budget = BudgetState(
            annual_revenue_brl_bi=float(budget_raw.get("annual_revenue_brl_bi", 2800)),
            mandatory_share=float(budget_raw.get("mandatory_share", 0.92)),
            fiscal_space_brl_bi=float(budget_raw.get("fiscal_space_brl_bi", 90)),
            fiscal_space_annual_cap_brl_bi=float(
                budget_raw.get("fiscal_space_annual_cap_brl_bi", 120)
            ),
            monthly_replenish_brl_bi=float(budget_raw.get("monthly_replenish_brl_bi", 6.5)),
            year_spent_brl_bi=0.0,
        )
        ministers = [
            Minister(
                portfolio=str(item.get("portfolio")),
                title=str(item.get("title")),
                name=str(item.get("name", "Indicação automática")),
                origin="automatic",
                loyalty=float(item.get("loyalty", 55)),
                competence=float(item.get("competence", 55)),
            )
            for item in (data.get("ministers") or [])
        ]
        breakdown_raw = data.get("approval_breakdown") or {}
        approval_breakdown = ApprovalBreakdown(
            regions={str(k): float(v) for k, v in (breakdown_raw.get("regions") or {}).items()},
            income={str(k): float(v) for k, v in (breakdown_raw.get("income") or {}).items()},
        )
        cabinet_mode = data.get("cabinet_mode") or "automatic"
        if cabinet_mode not in ("automatic", "player"):
            cabinet_mode = "automatic"
        branches = {str(k): float(v) for k, v in (data.get("branches") or {}).items()}
        agents: dict[str, AgentState] = {}
        for agent_id, raw in (data.get("agents") or {}).items():
            agents[agent_id] = AgentState(
                id=agent_id,
                name=raw.get("name", agent_id),
                interests=list(raw.get("interests") or []),
                influence=float(raw.get("influence", 50)),
                resources=float(raw.get("resources", 50)),
                stance=float(raw.get("stance", 0)),
            )
        for agent_id in AGENT_IDS:
            if agent_id not in agents:
                raise ConfigError(f"Agente obrigatório ausente em pre_inicio_brasil.md: {agent_id}")
        problems = [
            Problem(id=p["id"], title=p["title"], severity=float(p.get("severity", 5)))
            for p in (data.get("main_problems") or [])
        ]
        diplomacy = {str(k): float(v) for k, v in (data.get("diplomacy") or {}).items()}
        trade = {str(k): float(v) for k, v in (data.get("trade") or {}).items()}
        date = data.get("date") or {"year": 2027, "month": 1}
    except (TypeError, ValueError, KeyError, ValidationError) as exc:
        raise ConfigError(f"YAML de pre_inicio_brasil.md inválido: {exc}") from exc
    return {
        "indicators": indicators,
        "congress": congress,
        "branches": branches,
        "agents": agents,
        "problems": problems,
        "diplomacy": diplomacy,
        "trade": trade,
        "date": date,
        "lore": lore,
        "president": data.get("president") or {},
        "budget": budget,
        "ministers": ministers,
        "approval_breakdown": approval_breakdown,
        "cabinet_mode": cabinet_mode,
    }


def parse_world(path: Path | None = None) -> dict[str, Any]:
    data, lore = load_markdown(path or WORLD_CONFIG)
    try:
        powers: dict[str, PowerState] = {}
        for power_id, raw in (data.get("powers") or {}).items():
            iso = str(raw.get("iso", power_id))
            lat, lng = COUNTRY_COORDS.get(iso, (0.0, 0.0))
            powers[power_id] = PowerState(
                id=power_id,
                name=raw.get("name", COUNTRY_NAMES_PT.get(iso, power_id)),
                iso=iso,
                lat=float(raw.get("lat", lat)),
                lng=float(raw.get("lng", lng)),
                gdp_growth=float(raw.get("gdp_growth", 1.0)),
                inflation=float(raw.get("inflation", 3.0)),
                stability=float(raw.get("stability", 60)),
                military_posture=float(raw.get("military_posture", 50)),
                relation_brazil=float(raw.get("relation_brazil", 50)),
                trade_with_brazil_usd_bi=float(raw.get("trade_with_brazil_usd_bi", 0)),
                alignment=str(raw.get("alignment", "")),
                interests=list(raw.get("interests") or []),
                tensions=list(raw.get("tensions") or []),
            )
        orgs = {
            org_id: OrgState(
                id=org_id,
                name=raw.get("name", org_id),
                relation_brazil=float(raw.get("relation_brazil", 50)),
                notes=str(raw.get("notes", "")),
            )
            for org_id, raw in (data.get("orgs") or {}).items()
        }
        flashpoints = [
            Flashpoint(
                id=item["id"],
                title=item["title"],
                severity=float(item.get("severity", 5)),
                countries=list(item.get("countries") or []),
            )
            for item in (data.get("flashpoints") or [])
        ]
    except (TypeError, ValueError, KeyError, ValidationError) as exc:
        raise ConfigError(f"YAML de contexto_mundial.md inválido: {exc}") from exc
    return {"powers": powers, "orgs": orgs, "flashpoints": flashpoints, "lore": lore}
