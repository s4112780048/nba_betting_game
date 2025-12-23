from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q

from leaderboard.models import MonthlyScore, current_month_str
from games.models import Game


def home(request):
    now = timezone.now()
    today = timezone.localdate()

    upcoming = (
        Game.objects.select_related("home_team", "away_team")
        .exclude(start_time__isnull=True)
        .filter(
            Q(status="scheduled", start_time__gte=now)
            | Q(status="in_progress", start_time__date=today)
        )
        .order_by("start_time")[:10]
    )

    recent = (
        Game.objects.select_related("home_team", "away_team")
        .exclude(start_time__isnull=True)
        .filter(status="final")
        .order_by("-start_time")[:10]
    )

    month = current_month_str()
    top10 = (
        MonthlyScore.objects.select_related("user")
        .filter(month=month)
        .order_by("-profit", "-wins", "user__username")[:10]
    )

    return render(
        request,
        "core/home.html",
        {"upcoming": upcoming, "recent": recent, "month": month, "top10": top10},
    )
