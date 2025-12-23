# games/tasks.py
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .espn_client import EspnClient
from .models import Game, Team
from betting.services import settle_game


def _upsert_team(source: str, p) -> Team:
    obj, _ = Team.objects.update_or_create(
        source=source,
        source_team_id=p.source_team_id,
        defaults={
            "name": p.name,
            "abbr": p.abbr,
            "logo_url": p.logo_url,
        },
    )
    return obj


def _upsert_game(source: str, p, start_time_dt) -> Game:
    home = _upsert_team(source, p.home)
    away = _upsert_team(source, p.away)

    defaults = {
        "start_time": start_time_dt,
        "status": p.status,
        "home_team": home,
        "away_team": away,
        "home_score": p.home_score,
        "away_score": p.away_score,
        "raw_json": p.raw,
    }

    game, _ = Game.objects.update_or_create(
        source=source,
        source_game_id=p.source_game_id,
        defaults=defaults,
    )
    return game


@shared_task
def sync_scores_for_date(date_str: Optional[str] = None) -> int:
    """
    date_str: 'YYYY-MM-DD'；不給就用台北今天
    """
    if date_str:
        day = timezone.datetime.fromisoformat(date_str).date()
    else:
        day = timezone.localdate()

    client = EspnClient()
    payloads = client.fetch_scoreboard(day)

    n = 0
    for p in payloads:
        start_time_dt = None
        if p.start_time:
            # ESPN 的 date 是 ISO UTC，Django 會存成 aware
            start_time_dt = timezone.make_aware(timezone.datetime.fromisoformat(p.start_time.replace("Z", "+00:00")))

        _upsert_game("espn", p, start_time_dt)
        n += 1

    return n


@shared_task
def settle_finished_games_for_date(date_str: Optional[str] = None) -> int:
    """
    結算指定日期「已 final 且 pending」的比賽
    """
    if date_str:
        day = timezone.datetime.fromisoformat(date_str).date()
    else:
        day = timezone.localdate()

    # 用 start_time 日期來抓（你 model 沒有 game_date）
    start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
    end = start + timedelta(days=1)

    qs = Game.objects.filter(start_time__gte=start, start_time__lt=end, status="final", settlement_status="pending")
    cnt = 0
    for g in qs.order_by("id"):
        settle_game(g.id)
        cnt += 1
    return cnt


@shared_task
def sync_and_settle_today() -> dict:
    n = sync_scores_for_date()
    s = settle_finished_games_for_date()
    return {"synced": n, "settled_games": s}


@shared_task
def sync_and_settle_yesterday() -> dict:
    day = timezone.localdate() - timedelta(days=1)
    n = sync_scores_for_date(str(day))
    s = settle_finished_games_for_date(str(day))
    return {"synced": n, "settled_games": s, "date": str(day)}
