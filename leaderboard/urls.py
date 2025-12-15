from django.urls import path
from .views import current_board

urlpatterns = [
    path("", current_board, name="current"),
]
