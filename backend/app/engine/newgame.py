from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from app.config_loader import parse_brazil, parse_world
from app.constants import GameStatus
from app.engine.apply import push_history
from app.models import Difficulty, GameDate, GameState, ProviderId


def create_new_game(
    difficulty: Difficulty,
    provider: ProviderId,
    provider_model: str = "",
    name: str | None = None,
) -> GameState:
    brazil = parse_brazil()
    world = parse_world()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    game_id = uuid4().hex
    seed = int(hashlib.sha256(game_id.encode()).hexdigest()[:8], 16)
    date_raw = brazil["date"]
    date = GameDate(year=int(date_raw.get("year", 2027)), month=int(date_raw.get("month", 1)))
    indicators = dict(brazil["indicators"])
    indicators.setdefault("coalition_support", brazil["congress"].coalition_support)
    state = GameState(
        id=game_id,
        name=name or "Governo 2027",
        created_at=now,
        updated_at=now,
        difficulty=difficulty,
        provider=provider,
        provider_model=provider_model,
        status=GameStatus.PLAYING,
        date=date,
        seed=seed,
        indicators=indicators,
        budget=brazil["budget"],
        congress=brazil["congress"],
        branches=brazil["branches"],
        agents=brazil["agents"],
        powers=world["powers"],
        orgs=world["orgs"],
        flashpoints=world["flashpoints"],
        diplomacy=brazil["diplomacy"],
        trade=brazil["trade"],
        problems=brazil["problems"],
        ministers=brazil["ministers"],
        cabinet_mode=brazil["cabinet_mode"],
        approval_breakdown=brazil["approval_breakdown"],
        brazil_lore=brazil["lore"],
        world_lore=world["lore"],
        memory_summary=(
            "Campanha de 2026: as propostas ainda serão levadas às urnas. "
            "A posse em janeiro de 2027 depende do mandato que o eleitorado entregar."
        ),
        campaign_pending=True,
    )
    push_history(
        state,
        "system",
        "Campanha de 2026",
        "Antes da posse, apresente 3 a 5 propostas centrais. O eleitorado e o Congresso "
        "sairão das urnas; o motor calcula os números, a IA só classifica a plataforma.",
        ["BRA"],
    )
    return state
