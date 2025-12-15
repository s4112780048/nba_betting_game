from django.shortcuts import render
from django.utils import timezone
from games.models import Game

def home(request):
    now = timezone.now()
    upcoming = Game.objects.select_related("home_team","away_team").filter(
        start_time_utc__gte=now
    ).order_by("start_time_utc")[:10]
    return render(request, "core/home.html", {"upcoming": upcoming})
