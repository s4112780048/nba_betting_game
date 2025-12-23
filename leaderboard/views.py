# leaderboard/views.py
from __future__ import annotations

from django.db.models import Prefetch
from django.shortcuts import render

from .models import MonthlyScore, current_month_str


def leaderboard(request):
    """
    本月排行榜（MonthlyScore）
    - 顯示使用者裝備的徽章（shop.UserBadge.equipped=True）
    """
    month = current_month_str()

    # ✅ Prefetch：每個 user 只抓「已裝備」那一個徽章（通常你設計是一人只能裝備一個）
    try:
        from shop.models import UserBadge  # 避免 shop 未啟用時整個爆掉

        equipped_badge_prefetch = Prefetch(
            "user__userbadge_set",
            queryset=UserBadge.objects.select_related("badge").filter(equipped=True),
            to_attr="equipped_badges",  # 會掛在 user.equipped_badges（list）
        )
        qs = MonthlyScore.objects.select_related("user").prefetch_related(equipped_badge_prefetch)
    except Exception:
        qs = MonthlyScore.objects.select_related("user")

    rows = (
        qs.filter(month=month)
        .order_by("-profit", "-wins", "user__username")[:50]
    )

    return render(request, "leaderboard/current.html", {"month": month, "rows": rows})
