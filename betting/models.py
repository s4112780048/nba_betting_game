# betting/models.py
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from games.models import Game


class Bet(models.Model):
    PICK_CHOICES = (
        ("home", "Home Win"),
        ("away", "Away Win"),
    )
    STATUS_CHOICES = (
        ("open", "Open"),
        ("won", "Won"),
        ("lost", "Lost"),
        ("void", "Void"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bets",
    )
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="bets",
    )

    # ✅ default="home"：避免舊資料新增欄位時 makemigrations 一直問 default
    pick = models.CharField(max_length=10, choices=PICK_CHOICES, default="home")

    stake = models.BigIntegerField()

    # decimal odds，例如 1.91 → 191
    odds_x100 = models.PositiveIntegerField(default=200)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    payout = models.BigIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def potential_payout(self) -> int:
        return (int(self.stake) * int(self.odds_x100)) // 100

    def __str__(self) -> str:
        return f"Bet({self.user_id}) {self.game_id} pick={self.pick} stake={self.stake} status={self.status}"
