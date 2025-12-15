from django.contrib import admin
from .models import ShopItem, Inventory

@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "price", "active")
    list_filter = ("active",)
    search_fields = ("code", "name")

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("user", "item", "quantity")
    search_fields = ("user__username", "item__name", "item__code")
