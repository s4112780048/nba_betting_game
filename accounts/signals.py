from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Wallet, WalletTx

@receiver(post_save, sender=User)
def create_wallet(sender, instance, created, **kwargs):
    if created:
        w = Wallet.objects.create(user=instance, balance=1000)
        WalletTx.objects.create(wallet=w, type="init", amount=1000, note="Initial coins")
