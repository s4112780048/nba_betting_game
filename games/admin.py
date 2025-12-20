from django.contrib import admin
from .models import Game, Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    pass


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    pass
