from django.urls import path
from .views import game_list, game_detail

urlpatterns = [
    path("", game_list, name="list"),
    path("<int:game_id>/", game_detail, name="detail"),
]
