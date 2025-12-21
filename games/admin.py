from django.contrib import admin
from .models import Team, Game


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "source_team_id", "abbreviation", "name", "nba_team_id", "updated_at")
    search_fields = ("name", "abbreviation", "source_team_id", "nba_team_id")
    list_filter = ("source",)


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "source_game_id",
        "nba_game_id",
        "game_date",
        "status",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "is_final",
        "settled",
        "settled_at",
        "updated_at",
    )
    search_fields = ("source_game_id", "nba_game_id")
    list_filter = ("source", "status", "game_date", "settled")
