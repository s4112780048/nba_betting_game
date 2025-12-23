# betting/admin.py
from django.contrib import admin

from .models import Bet


@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "game",
        "pick",
        "pick_team",      # ✅ 這是下面補的 method
        "stake",
        "odds_x100",
        "status",
        "payout",
        "created_at",
        "settled_at",
    )
    list_filter = ("status", "pick", "created_at")
    search_fields = (
        "user__username",
        "game__source_game_id",
        "game__home_team__name",
        "game__away_team__name",
        "game__home_team__abbr",
        "game__away_team__abbr",
    )
    autocomplete_fields = ("user", "game")

    @admin.display(description="Pick Team")
    def pick_team(self, obj: Bet) -> str:
        """
        用 obj.pick ('home'/'away') 推出實際選到的隊伍
        """
        g = obj.game
        if not g:
            return ""
        if obj.pick == "home":
            return str(getattr(g, "home_team", "") or "")
        if obj.pick == "away":
            return str(getattr(g, "away_team", "") or "")
        return ""
