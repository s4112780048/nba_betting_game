from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import MonthlyScore, current_month_str


def current_board(request):
    month = current_month_str()
    rows = (
        MonthlyScore.objects.select_related("user")
        .filter(month=month)
        .order_by("-score", "user__username")[:50]
    )
    return render(request, "leaderboard/current.html", {"month": month, "rows": rows})
