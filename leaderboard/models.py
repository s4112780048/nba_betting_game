from django.conf import settings
from django.db import models

class MonthlySnapshot(models.Model):
    year = models.IntegerField()
    month = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class MonthlySnapshotRow(models.Model):
    snapshot = models.ForeignKey(MonthlySnapshot, on_delete=models.CASCADE, related_name="rows")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    points = models.IntegerField()
    rank = models.IntegerField()
