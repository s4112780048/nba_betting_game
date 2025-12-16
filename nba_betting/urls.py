from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("allauth.urls")),
    path("", include(("core.urls", "core"), namespace="core")),
    path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("games/", include(("games.urls", "games"), namespace="games")),
    path("shop/", include(("shop.urls", "shop"), namespace="shop")),
    path("leaderboard/", include(("leaderboard.urls", "leaderboard"), namespace="leaderboard")),
]

