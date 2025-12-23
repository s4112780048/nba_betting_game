# nba_betting/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Django built-in auth
    path("auth/", include("django.contrib.auth.urls")),

    # home
    path("", core_views.home, name="home"),

    # accounts app
    path("accounts/", include("accounts.urls")),
    path("accounts/profile/", RedirectView.as_view(url="/", permanent=False)),

    # other apps
    path("games/", include("games.urls")),
    path("betting/", include("betting.urls")),  # ✅ 下注功能
    path("shop/", include("shop.urls")),
    path("leaderboard/", include("leaderboard.urls")),
]
