# leaderboard/models.py
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils import timezone


def current_month_str(dt=None) -> str:
    """
    回傳 'YYYY-MM'，用於 MonthlyScore.month
    """
    if dt is None:
        dt = timezone.localdate()
    return f"{dt.year:04d}-{dt.month:02d}"


class MonthlyScoreQuerySet(models.QuerySet):
    def with_score(self):
        """
        ✅ 讓舊程式碼可以繼續用 score
        目前定義：score = profit（你也可以改成其他公式）
        """
        return self.annotate(score=F("profit"))


class MonthlyScoreManager(models.Manager.from_queryset(MonthlyScoreQuerySet)):
    def get_queryset(self):
        # ✅ 所有 MonthlyScore 查詢都自動帶 score annotation
        return super().get_queryset().with_score()


class MonthlyScore(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    month = models.CharField(max_length=7, db_index=True)  # 'YYYY-MM'

    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    volume = models.IntegerField(default=0)
    profit = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    # ✅ 關鍵：用自訂 manager
    objects = MonthlyScoreManager()

    class Meta:
        ordering = ("-profit", "-wins", "-volume", "user_id")
        indexes = [
            models.Index(fields=["month"]),
            models.Index(fields=["user", "month"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.month} profit={self.profit} W-L={self.wins}-{self.losses}"
