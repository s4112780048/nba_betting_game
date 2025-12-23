# betting/urls.py
from django.urls import path
from . import views

app_name = "betting"

urlpatterns = [
    path("place/<int:game_id>/", views.place_bet, name="place"),
]
