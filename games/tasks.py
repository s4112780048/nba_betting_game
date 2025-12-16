from celery import shared_task
from django.core.management import call_command

@shared_task
def sync_scores_last_2_days():
    # 回補最近 2 天（避免跨日/延遲結算）
    call_command("sync_nba_backfill", days=2, quiet=True)

@shared_task
def sync_schedule():
    # 更新未來賽程
    call_command("sync_nba_schedule")
