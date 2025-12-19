# games/admin.py
from django.contrib import admin
from .models import Team, Game


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("abbr", "name", "city")
    search_fields = ("abbr", "name", "city")
    ordering = ("abbr",)


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "source_game_id",
        "start_time_utc",
        "status",
        "away_team",
        "home_team",
        "away_score",
        "home_score",
        "winner",
        "settled_at",
        "updated_at",
    )
    list_filter = ("source", "status")
    search_fields = ("source_game_id", "home_team__abbr", "away_team__abbr")
    ordering = ("-start_time_utc",)
