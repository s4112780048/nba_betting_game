from django.conf import settings
from django.db import models


class MonthlyScore(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="monthly_scores")
    year = models.IntegerField()
    month = models.IntegerField()
    points = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "year", "month")
        indexes = [
            models.Index(fields=["year", "month", "-points"]),
        ]

    def __str__(self):
        return f"{self.user} {self.year}-{self.month:02d} pts={self.points}"
