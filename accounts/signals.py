# accounts/signals.py
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Wallet


User = get_user_model()


@receiver(post_save, sender=User)
def ensure_wallet(sender, instance, created, **kwargs):
    # 使用者建立時自動建立 wallet（已存在就略過）
    if created:
        Wallet.objects.get_or_create(user=instance)
