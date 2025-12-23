# nba_betting/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nba_betting.settings")

app = Celery("nba_betting")

# 從 Django settings 讀取 CELERY_ 開頭的設定
app.config_from_object("django.conf:settings", namespace="CELERY")

# 讓 shared_task 自動掃到各 app 的 tasks.py
app.autodiscover_tasks()

# 部署環境常見：Redis 一開始還沒就緒，這個可避免 worker 啟動直接死
app.conf.broker_connection_retry_on_startup = True

# 讓 task 執行狀態比較好追
app.conf.task_track_started = True
