from django.shortcuts import render
from django.utils import timezone
from betting.models import MonthlyScore

def current_board(request):
    now = timezone.localtime(timezone.now())
    scores = MonthlyScore.objects.select_related("user").filter(
        year=now.year, month=now.month
    ).order_by("-points")[:50]
    return render(request, "leaderboard/current.html", {"scores": scores, "year": now.year, "month": now.month})
