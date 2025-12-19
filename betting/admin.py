from django.contrib import admin
from .models import Bet


@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "game", "pick_team", "stake", "status", "payout", "created_at", "settled_at")
    list_filter = ("status",)
    search_fields = ("user__username", "game__nba_game_id")
