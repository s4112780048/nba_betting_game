from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .espn_client import EspnClient, EspnGame
from .models import Game, Team


def _to_date(date_str: Optional[str]) -> date:
    if not date_str:
        return timezone.localdate()
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _get_or_create_team(source: str, abbr: str, name: str = "") -> Team:
    # 用 (source, abbreviation) 當最穩定的 key（ESPN team id 我們之後再補）
    obj, _ = Team.objects.get_or_create(
        source=source,
        abbreviation=abbr,
        defaults={"name": name or abbr},
    )
    # 補齊 name
    if name and (not obj.name):
        obj.name = name
        obj.save(update_fields=["name"])
    return obj


def _set_winner(game: Game) -> None:
    # 前提：is_final=True 且有比分
    if game.home_team and game.away_team and game.home_score is not None and game.away_score is not None:
        if game.home_score > game.away_score:
            game.winner = game.home_team
        elif game.away_score > game.home_score:
            game.winner = game.away_team
        else:
            game.winner = None  # 平手（NBA 一般不會）
    else:
        game.winner = None


def _upsert_game_from_espn(g: EspnGame, day: date) -> Game:
    home = _get_or_create_team(g.source, g.home.abbreviation, g.home.display_name)
    away = _get_or_create_team(g.source, g.away.abbreviation, g.away.display_name)

    obj, _created = Game.objects.get_or_create(
        source=g.source,
        source_game_id=g.source_game_id,
        defaults={"game_date": day},
    )

    obj.game_date = day
    obj.status = g.status or "pre"

    obj.home_team = home
    obj.away_team = away
    obj.home_abbr = g.home.abbreviation
    obj.away_abbr = g.away.abbreviation
    obj.home_score = int(g.home.score or 0)
    obj.away_score = int(g.away.score or 0)

    # ESPN: post = final
    obj.is_final = (obj.status == "post")

    if obj.is_final:
        _set_winner(obj)

    obj.save()
    return obj


@shared_task
def sync_scores_for_date(date_str: Optional[str] = None) -> dict:
    day = _to_date(date_str)
    client = EspnClient()
    games = client.fetch_scoreboard(day)

    upserted = 0
    for g in games:
        _upsert_game_from_espn(g, day)
        upserted += 1

    return {"ok": True, "date": day.isoformat(), "upserted": upserted}


@shared_task
def settle_finished_games_for_date(date_str: Optional[str] = None) -> dict:
    """
    結算指定日期已 final 的比賽，且 settled=False 才結算。
    注意：延遲 import betting.services，避免 circular import / settings not ready。
    """
    from betting.services import settle_game  # 延遲 import

    day = _to_date(date_str)
    qs = Game.objects.filter(game_date=day, is_final=True, settled=False)

    settled_count = 0
    for game in qs.select_for_update():
        with transaction.atomic():
            ok = settle_game(game_id=game.id)
            if ok:
                settled_count += 1

    return {"ok": True, "date": day.isoformat(), "settled": settled_count}


@shared_task
def sync_and_settle_date(date_str: Optional[str] = None) -> dict:
    day = _to_date(date_str)
    a = sync_scores_for_date(day.isoformat())
    b = settle_finished_games_for_date(day.isoformat())
    return {"ok": True, "date": day.isoformat(), "sync": a, "settle": b}


@shared_task
def sync_and_settle_today() -> dict:
    return sync_and_settle_date(timezone.localdate().isoformat())


@shared_task
def sync_and_settle_yesterday() -> dict:
    return sync_and_settle_date((timezone.localdate() - timedelta(days=1)).isoformat())
