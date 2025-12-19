# leaderboard/admin.py
from django.contrib import admin
from .models import MonthlyScore

@admin.register(MonthlyScore)
class MonthlyScoreAdmin(admin.ModelAdmin):
    list_display = ("month", "user", "profit", "wins", "losses", "volume", "updated_at")
    list_filter = ("month",)
    search_fields = ("user__username",)
