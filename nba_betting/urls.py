# nba_betting/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    path("games/", include(("games.urls", "games"), namespace="games")),
    path("leaderboard/", include(("leaderboard.urls", "leaderboard"), namespace="leaderboard")),

    # allauth（要 Google 登入才需要）
    path("accounts/", include("allauth.urls")),

    # 你原本的 accounts app（若你保留本機帳密登入）
    path("accounts-app/", include(("accounts.urls", "accounts"), namespace="accounts")),

    path("", include(("core.urls", "core"), namespace="core")),
]
