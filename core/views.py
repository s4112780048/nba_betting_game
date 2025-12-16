from django.shortcuts import render
from django.utils import timezone

from games.models import Game
from shop.models import ShopItem
from leaderboard.models import MonthlyScore
from accounts.models import Wallet


def home(request):
    now = timezone.now()

    upcoming = (
        Game.objects.select_related("home_team", "away_team")
        .filter(start_time_utc__gte=now)
        .order_by("start_time_utc")[:8]
    )

    # 本月排行榜 Top 10
    y, m = now.year, now.month
    top10 = (
        MonthlyScore.objects.select_related("user")
        .filter(year=y, month=m)
        .order_by("-points")[:10]
    )

    # 商店精選
    featured_items = ShopItem.objects.filter(active=True).order_by("price")[:6]

    wallet = None
    if request.user.is_authenticated:
        wallet = Wallet.objects.filter(user=request.user).first()

    return render(
        request,
        "core/home.html",
        {
            "upcoming": upcoming,
            "top10": top10,
            "featured_items": featured_items,
            "wallet": wallet,
            "year": y,
            "month": m,
        },
    )
