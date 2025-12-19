# games/tasks.py
from datetime import timedelta
from celery import shared_task
from django.core.management import call_command
from django.utils import timezone

from games.models import Game
from betting.services import settle_game_bets


@shared_task
def sync_scores_and_settle():
    # 1) 同步：過去 2 天 + 未來 7 天（賽程）
    call_command("sync_scores_espn", days=2, forward=7, quiet=True)

    # 2) 結算：找 final 且 winner 不為空，且未 settled
    since = timezone.now() - timedelta(days=3)
    qs = Game.objects.filter(start_time_utc__gte=since, status=3).exclude(winner=None).filter(settled_at__isnull=True)

    settled = 0
    for g in qs:
        settled += settle_game_bets(g)

    return {"final_games": qs.count(), "bets_settled": settled}
