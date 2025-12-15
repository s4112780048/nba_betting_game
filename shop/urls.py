from django.urls import path
from .views import shop_list, buy_item, inventory_view

urlpatterns = [
    path("", shop_list, name="list"),
    path("buy/<int:item_id>/", buy_item, name="buy"),
    path("inventory/", inventory_view, name="inventory"),
]
