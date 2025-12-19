from django.conf import settings
from django.db import models
from django.utils import timezone

from games.models import Game, Team


class Bet(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        WON = "WON", "Won"
        LOST = "LOST", "Lost"
        VOID = "VOID", "Void"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bets")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="bets")

    pick_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="picked_bets")
    stake = models.PositiveIntegerField()

    # 先用最簡單：贏了固定拿回 stake*2（含本金） => 淨賺 stake
    payout = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} bet {self.pick_team} on {self.game} ({self.status})"
