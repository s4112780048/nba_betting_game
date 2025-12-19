from celery import shared_task
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta

from games.models import Game
from betting.services import settle_game_bets


@shared_task
def sync_scores_last_2_days():
    # 回補最近 2 天比分（你的 command）
    call_command("sync_nba_backfill", days=2, quiet=True)

    # ✅ 回補完，結算最近 3 天 final 的比賽（保守一點）
    since = timezone.now() - timedelta(days=3)
    qs = Game.objects.filter(start_time_utc__gte=since, status=3).exclude(winner=None)

    settled = 0
    for g in qs:
        settled += settle_game_bets(g)

    return {"final_games": qs.count(), "bets_settled": settled}


@shared_task
def sync_schedule():
    call_command("sync_nba_schedule")
    return {"ok": True}
