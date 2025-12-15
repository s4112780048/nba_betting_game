from django.conf import settings
from django.db import models, transaction

class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    balance = models.IntegerField(default=1000)

    def __str__(self):
        return f"{self.user.username} ({self.balance})"

class WalletTx(models.Model):
    class Type(models.TextChoices):
        INIT = "init"
        BET = "bet"
        PAYOUT = "payout"
        PURCHASE = "purchase"
        REWARD = "reward"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="txs")
    type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.IntegerField()  # +進帳 / -支出
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

def wallet_add(wallet: Wallet, amount: int, tx_type: str, note: str = ""):
    with transaction.atomic():
        w = Wallet.objects.select_for_update().get(pk=wallet.pk)
        w.balance += amount
        if w.balance < 0:
            raise ValueError("Insufficient balance")
        w.save(update_fields=["balance"])
        WalletTx.objects.create(wallet=w, type=tx_type, amount=amount, note=note)
        return w
