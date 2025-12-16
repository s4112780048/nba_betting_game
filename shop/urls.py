from django.urls import path
from . import views

app_name = "shop"

urlpatterns = [
    path("", views.shop_list, name="list"),
    path("buy/<int:item_id>/", views.buy_item, name="buy"),
    path("inventory/", views.inventory, name="inventory"),
    path("open/<int:inv_id>/", views.open_lootbox, name="open"),
    path("equip/<int:badge_id>/", views.equip_badge, name="equip_badge"),
]
