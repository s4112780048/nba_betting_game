from django.conf import settings
from django.db import models

class ShopItem(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=60)
    price = models.IntegerField()
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Inventory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    item = models.ForeignKey(ShopItem, on_delete=models.PROTECT)
    quantity = models.IntegerField(default=0)

    class Meta:
        unique_together = [("user", "item")]
