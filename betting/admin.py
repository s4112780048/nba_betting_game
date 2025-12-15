from django.contrib import admin
from .models import Bet, MonthlyScore

@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = ("user", "game", "pick_team", "stake", "status", "payout", "points", "placed_at")
    list_filter = ("status",)
    search_fields = ("user__username", "game__nba_game_id")

@admin.register(MonthlyScore)
class MonthlyScoreAdmin(admin.ModelAdmin):
    list_display = ("user", "year", "month", "points")
    list_filter = ("year", "month")
    search_fields = ("user__username",)
