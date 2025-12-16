from celery import shared_task

@shared_task
def leaderboard_monthly_snapshot():
    """
    如果你還沒做 MonthlySnapshot 這張表，就先不要在檔案頂部 import 它。
    需要時再在函式內匯入，避免 Django 啟動（含 admin）直接 500。
    """
    from .models import MonthlySnapshot  # ✅ 延遲匯入：進到 task 才 import

    # TODO: 你的快照邏輯寫這裡
    # MonthlySnapshot.objects.create(...)
    return "ok"
