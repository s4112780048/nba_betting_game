# leaderboard/urls.py
from django.urls import path
from .views import current_board

app_name = "leaderboard"

urlpatterns = [
    path("", current_board, name="current"),
]
