from celery import shared_task
from django.core.management import call_command


@shared_task
def update_scores_daily(days: int = 14):
    """
    每天跑一次：回補最近 N 天已完賽比分/勝負（安全可重複執行）
    """
    call_command("sync_nba_backfill", days=days, quiet=True)
    return f"backfill ok days={days}"


@shared_task
def update_scores_frequent():
    """
    比較頻繁的更新（可選）：
    - 如果你有 sync_nba_today：就跑它（更新今天 live/final）
    - 沒有的話就改跑 backfill 2 天，避免漏比分
    """
    try:
        call_command("sync_nba_today")
        return "today ok"
    except Exception:
        call_command("sync_nba_backfill", days=2, quiet=True)
        return "fallback backfill 2 days ok"
