# games/admin.py
from django.contrib import admin
from .models import Team, Game


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "source_team_id", "abbr", "name", "updated_at")
    list_filter = ("source",)
    search_fields = ("name", "abbr", "source_team_id")


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "source_game_id",
        "start_time",
        "status",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "settlement_status",
        "settled_at",
        "updated_at",
    )
    list_filter = ("source", "status", "settlement_status")

    # ✅ 這行是為了 BetAdmin.autocomplete_fields = ("game",) 必須存在
    search_fields = (
        "source_game_id",
        "home_team__name",
        "away_team__name",
        "home_team__abbr",
        "away_team__abbr",
    )

    autocomplete_fields = ("home_team", "away_team")
