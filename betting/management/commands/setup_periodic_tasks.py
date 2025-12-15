from django.core.management.base import BaseCommand
from django.conf import settings
from django_celery_beat.models import PeriodicTask, CrontabSchedule

def _has_field(model, field_name: str) -> bool:
    return any(f.name == field_name for f in model._meta.fields)

class Command(BaseCommand):
    help = "Create/update Celery Beat periodic tasks (schedule + settle)."

    def handle(self, *args, **options):
        tz = getattr(settings, "TIME_ZONE", "UTC")

        # every 5 minutes
        cron_5min_kwargs = dict(minute="*/5", hour="*", day_of_week="*", day_of_month="*", month_of_year="*")
        if _has_field(CrontabSchedule, "timezone"):
            cron_5min_kwargs["timezone"] = tz
        cron_5min, _ = CrontabSchedule.objects.get_or_create(**cron_5min_kwargs)

        # daily 09:00
        cron_daily_kwargs = dict(minute="0", hour="9", day_of_week="*", day_of_month="*", month_of_year="*")
        if _has_field(CrontabSchedule, "timezone"):
            cron_daily_kwargs["timezone"] = tz
        cron_daily, _ = CrontabSchedule.objects.get_or_create(**cron_daily_kwargs)

        PeriodicTask.objects.update_or_create(
            name="NBA: sync today & settle (every 5 min)",
            defaults={
                "task": "betting.tasks.sync_today_and_settle",
                "crontab": cron_5min,
                "enabled": True,
            },
        )

        PeriodicTask.objects.update_or_create(
            name="NBA: sync schedule (daily 09:00)",
            defaults={
                "task": "betting.tasks.sync_schedule",
                "crontab": cron_daily,
                "enabled": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("Periodic tasks created/updated OK."))
