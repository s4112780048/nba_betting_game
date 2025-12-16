from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),   # ✅ 新增
    path("logout/", views.logout_view, name="logout"),
    path("wallet/", views.wallet_view, name="wallet"),
    path("daily-bonus/", views.daily_bonus, name="daily_bonus"),
]
