from celery import shared_task
from django.apps import apps
from django.utils import timezone


@shared_task
def leaderboard_monthly_snapshot():
    """
    每月結算/快照（先讓 admin 不爆）
    你目前 models.py 沒有 MonthlySnapshot，所以用 apps.get_model 延遲取得。
    找不到就直接跳過，避免整個系統掛掉。
    """
    try:
        MonthlySnapshot = apps.get_model("leaderboard", "MonthlySnapshot")
    except LookupError:
        # 你目前沒有這個 model，先不要讓匯入就爆掉
        return "Skipped: MonthlySnapshot model not found."

    # ✅ 如果你之後真的加了 MonthlySnapshot，才把下面邏輯補上
    # 這裡先給一個最小可運行範例（不假設你的欄位）
    # e.g. MonthlySnapshot.objects.create(month=timezone.localdate().replace(day=1), ...)
    return "Monthly snapshot task placeholder OK."
