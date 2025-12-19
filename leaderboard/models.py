# leaderboard/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone

def current_month_str(dt=None) -> str:
    if dt is None:
        dt = timezone.now()
    dt = timezone.localtime(dt)
    return dt.strftime("%Y-%m")

class MonthlyScore(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    month = models.CharField(max_length=7, db_index=True)  # YYYY-MM

    profit = models.IntegerField(default=0)  # 淨利
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    volume = models.IntegerField(default=0)  # 總下注額

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "month")
        indexes = [
            models.Index(fields=["month", "-profit"]),
        ]

    def __str__(self):
        return f"{self.month} {self.user} profit={self.profit}"
