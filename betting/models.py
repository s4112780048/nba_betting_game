# betting/models.py
from django.conf import settings
from django.db import models

from games.models import Game, Team

class Bet(models.Model):
    STATUS_CHOICES = [
        ("OPEN", "OPEN"),
        ("SETTLED", "SETTLED"),
        ("CANCELLED", "CANCELLED"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="bets")
    pick_team = models.ForeignKey(Team, on_delete=models.PROTECT)

    stake = models.IntegerField()
    payout = models.IntegerField(default=0)  # 贏了實拿（不含原本扣掉的 stake）
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="OPEN")

    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "game"], name="uniq_bet_per_user_per_game")
        ]

    def __str__(self):
        return f"{self.user} {self.game} pick={self.pick_team.abbr} stake={self.stake} {self.status}"
