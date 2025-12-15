from django.contrib import admin
from .models import Team, Game

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("nba_team_id", "abbr", "name", "city")
    search_fields = ("abbr", "name", "city")

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("nba_game_id", "start_time_utc", "away_team", "home_team", "status", "away_score", "home_score")
    list_filter = ("status",)
    search_fields = ("nba_game_id", "away_team__abbr", "home_team__abbr")
