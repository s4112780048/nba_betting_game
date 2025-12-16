from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .models import Game
from betting.services import place_bet


def game_list(request):
    now = timezone.now()
    window_days = 14
    recent_start = now - timedelta(days=window_days)

    # ✅ 未來賽程：時間在現在之後（不管 status=1/2）
    upcoming = (
        Game.objects.select_related("home_team", "away_team")
        .filter(start_time_utc__gte=now)
        .order_by("start_time_utc")[:50]
    )

    # ✅ Live：status=2（可選）
    live = (
        Game.objects.select_related("home_team", "away_team")
        .filter(status=2)
        .order_by("start_time_utc")[:30]
    )

    # ✅ 最近比賽：最近 14 天、且已經開打過（start_time < now）
    #    不強制 status=3，避免你「Final 沒更新」就完全看不到
    recent = (
        Game.objects.select_related("home_team", "away_team")
        .filter(start_time_utc__lt=now, start_time_utc__gte=recent_start)
        .order_by("-start_time_utc")[:80]
    )

    return render(
        request,
        "games/game_list.html",
        {
            "upcoming": upcoming,
            "recent": recent,
            "live": live,  # 你模板想用再加，不用也不影響
        },
    )


@login_required
def game_detail(request, game_id):
    game = get_object_or_404(
        Game.objects.select_related("home_team", "away_team"),
        pk=game_id
    )

    if request.method == "POST":
        pick = request.POST.get("pick")  # home/away
        stake = int(request.POST.get("stake", "0"))
        pick_team = game.home_team if pick == "home" else game.away_team
        try:
            place_bet(request.user, game, pick_team, stake)
            return redirect("accounts:wallet")
        except Exception as e:
            return render(request, "games/game_detail.html", {"game": game, "error": str(e)})

    return render(request, "games/game_detail.html", {"game": game})
