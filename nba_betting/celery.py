# nba_betting/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nba_betting.settings")

app = Celery("nba_betting")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
