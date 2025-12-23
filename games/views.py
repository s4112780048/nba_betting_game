# games/views.py
from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Game


def game_list(request):
    now = timezone.now()
    today = timezone.localdate()

    upcoming = (
        Game.objects.select_related("home_team", "away_team")
        .exclude(start_time__isnull=True)
        .filter(
            Q(status="scheduled", start_time__gte=now)
            | Q(status="in_progress", start_time__date=today)
        )
        .order_by("start_time")[:200]
    )

    recent = (
        Game.objects.select_related("home_team", "away_team")
        .exclude(start_time__isnull=True)
        .filter(status="final")
        .order_by("-start_time")[:200]
    )

    return render(request, "games/game_list.html", {"upcoming": upcoming, "recent": recent})


def game_detail(request, game_id: int):
    game = get_object_or_404(Game.objects.select_related("home_team", "away_team"), pk=game_id)

    winner = ""
    if game.home_score is not None and game.away_score is not None:
        if game.home_score > game.away_score:
            winner = game.home_team.abbr or game.home_team.name
        elif game.away_score > game.home_score:
            winner = game.away_team.abbr or game.away_team.name
        else:
            winner = "Tie"

    return render(
        request,
        "games/game_detail.html",
        {
            "game": game,  # ✅ 新版用 game
            "g": game,     # ✅ 兼容你舊模板用 g
            "winner": winner,
        },
    )
