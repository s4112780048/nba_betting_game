from celery import shared_task
from django.utils import timezone
from betting.models import MonthlyScore
from .models import MonthlySnapshot, MonthlySnapshotRow
from accounts.models import Wallet, WalletTx, wallet_add

@shared_task
def close_previous_month_and_reset():
    now = timezone.localtime(timezone.now())
    year, month = now.year, now.month

    # 取上個月
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)

    scores = list(MonthlyScore.objects.filter(year=prev_year, month=prev_month).select_related("user")
                  .order_by("-points"))

    if not scores:
        return "no scores"

    snap = MonthlySnapshot.objects.create(year=prev_year, month=prev_month)

    # 產生排名 + 發獎（例：前 3 名發 coin）
    rewards = [500, 300, 100]
    for idx, s in enumerate(scores, start=1):
        MonthlySnapshotRow.objects.create(snapshot=snap, user=s.user, points=s.points, rank=idx)

        if idx <= 3:
            w = Wallet.objects.get(user=s.user)
            wallet_add(w, rewards[idx-1], "reward", note=f"Monthly reward {prev_year}-{prev_month:02d} rank {idx}")

    # 重置：其實不必刪，因為新月份會 get_or_create；你也可保留歷史
    return f"snapshot created: {prev_year}-{prev_month:02d}, rows={len(scores)}"
