from celery import shared_task
from django.core.management import call_command

@shared_task
def sync_schedule():
    call_command("sync_nba_schedule")

@shared_task
def sync_today_and_settle():
    call_command("sync_nba_today")
