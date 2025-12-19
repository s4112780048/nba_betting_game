from django.shortcuts import render
from django.utils import timezone

from leaderboard.models import MonthlyScore, current_month_str
from games.models import Game


def home(request):
    # 取即將開賽 & 最近比賽（讓首頁有內容）
    now = timezone.now()
    upcoming = (
        Game.objects.select_related("home_team", "away_team")
        .filter(status=1, start_time_utc__gte=now)
        .order_by("start_time_utc")[:10]
    )
    recent = (
        Game.objects.select_related("home_team", "away_team")
        .filter(status=3)
        .order_by("-start_time_utc")[:10]
    )

    # 本月排行榜 Top 10
    month = current_month_str()
    top10 = (
        MonthlyScore.objects.select_related("user")
        .filter(month=month)
        .order_by("-score", "user__username")[:10]
    )

    return render(
        request,
        "core/home.html",
        {"upcoming": upcoming, "recent": recent, "month": month, "top10": top10},
    )
