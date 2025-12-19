from django.conf import settings
from django.db import models
from django.utils import timezone


class MonthlyScore(models.Model):
    """
    每月積分（for 排行榜）
    month 格式：YYYY-MM，例如 2025-12
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monthly_scores")
    month = models.CharField(max_length=7, db_index=True)
    score = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "month")
        ordering = ("-score", "user_id")

    def __str__(self):
        return f"{self.month} {self.user} score={self.score}"


def current_month_str():
    # 以台北時區的 today 來算月份
    today = timezone.localdate()
    return f"{today.year:04d}-{today.month:02d}"
