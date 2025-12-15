from django.conf import settings
from django.db import models
from games.models import Game, Team

class Bet(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        WON = "won"
        LOST = "lost"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    pick_team = models.ForeignKey(Team, on_delete=models.PROTECT)
    stake = models.IntegerField()
    payout = models.IntegerField(default=0)
    points = models.IntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    placed_at = models.DateTimeField(auto_now_add=True)

class MonthlyScore(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    points = models.IntegerField(default=0)

    class Meta:
        unique_together = [("user", "year", "month")]
