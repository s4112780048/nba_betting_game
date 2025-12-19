# leaderboard/views.py
from django.shortcuts import render
from django.utils import timezone
from .models import MonthlyScore, current_month_str

def current_board(request):
    month = request.GET.get("month") or current_month_str()
    rows = (
        MonthlyScore.objects.select_related("user")
        .filter(month=month)
        .order_by("-profit", "-wins", "-volume")[:100]
    )
    return render(request, "leaderboard/current_board.html", {"rows": rows, "month": month})
