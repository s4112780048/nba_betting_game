from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("wallet/", views.wallet_view, name="wallet"),
    path("deposit/", views.deposit, name="deposit"),
    path("withdraw/", views.withdraw, name="withdraw"),
    path("daily-bonus/", views.daily_bonus, name="daily_bonus"),
]




