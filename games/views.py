# games/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .models import Game
from betting.services import place_bet

def game_list(request):
    now = timezone.now()

    upcoming = (
        Game.objects.select_related("home_team", "away_team")
        .filter(status=1, start_time_utc__gte=now)
        .order_by("start_time_utc")[:80]
    )

    recent = (
        Game.objects.select_related("home_team", "away_team")
        .filter(status=3)
        .order_by("-start_time_utc")[:80]
    )

    return render(request, "games/game_list.html", {"upcoming": upcoming, "recent": recent})


@login_required
def game_detail(request, game_id):
    game = get_object_or_404(
        Game.objects.select_related("home_team", "away_team"),
        pk=game_id
    )

    if request.method == "POST":
        pick = request.POST.get("pick")  # "home" or "away"
        stake = int(request.POST.get("stake", "0") or 0)
        pick_team = game.home_team if pick == "home" else game.away_team

        try:
            place_bet(request.user, game, pick_team, stake)
            return redirect("accounts:wallet")
        except Exception as e:
            return render(request, "games/game_detail.html", {"game": game, "error": str(e)})

    return render(request, "games/game_detail.html", {"game": game})
