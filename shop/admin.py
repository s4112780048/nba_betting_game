from django.contrib import admin
from .models import Badge, ShopItem, InventoryItem, UserBadge, LootOpenLog

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "emoji", "rarity")
    search_fields = ("code", "name")

@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "price", "active")
    list_filter = ("kind", "active")
    search_fields = ("code", "name")

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("user", "item", "qty", "updated_at")
    search_fields = ("user__username", "item__code")

@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "badge", "equipped", "acquired_at")
    list_filter = ("equipped",)
    search_fields = ("user__username", "badge__code")

@admin.register(LootOpenLog)
class LootOpenLogAdmin(admin.ModelAdmin):
    list_display = ("user", "source_item", "reward_type", "coins", "badge", "created_at")
    list_filter = ("reward_type",)
    search_fields = ("user__username",)
