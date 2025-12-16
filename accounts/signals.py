from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.utils import OperationalError, ProgrammingError

from .models import Wallet, WalletTx


@receiver(post_save, sender=User)
def ensure_wallet(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        w, made = Wallet.objects.get_or_create(user=instance, defaults={"balance": 1000})
        if made:
            WalletTx.objects.create(wallet=w, type="init", amount=1000, note="Initial coins")
    except (OperationalError, ProgrammingError):
        return
