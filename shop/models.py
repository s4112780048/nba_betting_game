from django.conf import settings
from django.db import models
from django.utils import timezone


class Badge(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    emoji = models.CharField(max_length=10, default="🏀")
    rarity = models.IntegerField(default=1)  # 1 common, 2 rare, 3 epic

    def __str__(self):
        return f"{self.emoji} {self.name}"


class ShopItem(models.Model):
    KIND_CHOICES = [
        ("LOOT_BOX", "Loot Box"),
        ("BADGE", "Badge"),
        ("GENERIC", "Generic"),
    ]

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    price = models.IntegerField(default=100)
    active = models.BooleanField(default=True)

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="GENERIC")
    payload = models.JSONField(default=dict, blank=True)
    image_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.code} ({self.kind})"


class InventoryItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    item = models.ForeignKey(ShopItem, on_delete=models.CASCADE)
    qty = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "item")

    def __str__(self):
        return f"{self.user} {self.item.code} x{self.qty}"


class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    acquired_at = models.DateTimeField(default=timezone.now)
    equipped = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "badge")

    def __str__(self):
        return f"{self.user} {self.badge} equipped={self.equipped}"


class LootOpenLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source_item = models.ForeignKey(ShopItem, on_delete=models.SET_NULL, null=True, blank=True)
    reward_type = models.CharField(max_length=20)  # "coins" / "badge"
    coins = models.IntegerField(default=0)
    badge = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user} {self.reward_type}"
