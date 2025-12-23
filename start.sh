#!/usr/bin/env bash
set -e

echo "==> collectstatic"
python manage.py collectstatic --noinput

echo "==> migrate"
python manage.py migrate --noinput

# 建議：你有 setup_periodic_tasks 就順手跑一次（要寫成可重複執行、idempotent）
echo "==> setup periodic tasks (ignore if not exists)"
python manage.py setup_periodic_tasks || true

echo "==> start gunicorn"
exec gunicorn nba_betting.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 120
