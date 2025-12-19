# games/tasks.py
from __future__ import annotations

from celery import shared_task
from celery.utils.log import get_task_logger
from datetime import timedelta
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def sync_scores_last_2_days(self):
    """
    更新比分 + 結算（推薦順序）
    1) ESPN：補 status / scores（最穩、最重要）
    2) NBA backfill：能跑就補 teamId / schedule / winner
    3) settle：結算最近幾天已 Final 的比賽
    """
    from django.core.management import call_command
    from games.models import Game
    from betting.services import settle_game_bets

    # 1) ESPN 先補最近 2 天（你可以改 3 天更保守）
    try:
        call_command("sync_scores_espn", days=2, quiet=True)
        logger.info("ESPN sync done")
    except Exception as e:
        logger.exception("ESPN sync failed: %s", e)

    # 2) 再跑 NBA CDN backfill（如果 403 也沒關係）
    try:
        call_command("sync_nba_backfill", days=2, quiet=True)
        logger.info("NBA backfill done")
    except Exception as e:
        logger.warning("NBA backfill failed (ok to ignore if 403): %s", e)

    # 3) 結算：抓最近 3 天 final 且 winner 不為空
    since = timezone.now() - timedelta(days=3)
    qs = (
        Game.objects
        .filter(start_time_utc__gte=since, status=3)
        .exclude(winner=None)
        .order_by("-start_time_utc")
    )

    settled = 0
    final_games = qs.count()

    for g in qs:
        try:
            # settle_game_bets 建議設計成「已結算的不會重複發錢」
            settled += int(settle_game_bets(g) or 0)
        except Exception as e:
            logger.exception("settle failed game_id=%s err=%s", getattr(g, "id", None), e)

    result = {"final_games": final_games, "bets_settled": settled}
    logger.info("sync_scores_last_2_days done: %s", result)
    return result


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def sync_schedule(self):
    """
    更新未來賽程（你原本的）
    """
    from django.core.management import call_command

    call_command("sync_nba_schedule")
    logger.info("sync_schedule done")
    return {"ok": True}
