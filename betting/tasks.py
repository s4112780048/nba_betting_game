from celery import shared_task
from django.core.management import call_command

from .settle import settle_finished_games


@shared_task
def sync_schedule():
    call_command("sync_nba_schedule")


@shared_task
def sync_scores_last_2_days():
    # 你現在的回補 command（或 ESPN sync）用哪個就留哪個
    call_command("sync_nba_backfill", days=2, quiet=True)


@shared_task
def settle_bets_task():
    return settle_finished_games(limit_games=300)


@shared_task
def sync_and_settle():
    # 一鍵：更新比分 → 結算
    call_command("sync_nba_backfill", days=2, quiet=True)
    return settle_finished_games(limit_games=300)
