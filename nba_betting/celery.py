import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nba_betting.settings")

app = Celery("nba_betting")

# ✅ 讓 Celery 讀 Django settings 裡 CELERY_ 開頭的設定
app.config_from_object("django.conf:settings", namespace="CELERY")

# ✅ 自動找各 app 的 tasks.py
app.autodiscover_tasks()
