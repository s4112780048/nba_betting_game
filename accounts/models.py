from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.BigIntegerField(default=0)

    # ✅ 每日簽到用
    last_checkin_date = models.DateField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} balance={self.balance}"


class Transaction(models.Model):
    TYPE_CHOICES = (
        ("deposit", "Deposit"),
        ("withdraw", "Withdraw"),
        ("bet_place", "Bet Place"),
        ("bet_win", "Bet Win"),
        ("bet_refund", "Bet Refund"),
        ("daily_bonus", "Daily Bonus"),
        ("shop_buy", "Shop Buy"),
        ("lootbox", "Loot Box"),
        ("adjust", "Adjust"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="txs")
    tx_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.BigIntegerField()
    ref = models.CharField(max_length=128, blank=True, default="")
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["wallet", "created_at"])]

    def __str__(self):
        return f"{self.tx_type} {self.amount} ({self.wallet.user})"


def get_or_create_wallet(user) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def _apply_balance(wallet_id: int, amount: int):
    Wallet.objects.filter(pk=wallet_id).update(balance=F("balance") + int(amount))


def wallet_add(wallet: Wallet, amount: int, tx_type: str = "adjust", ref: str = "", note: str = "") -> Transaction:
    if amount <= 0:
        raise ValueError("amount must be > 0")
    with transaction.atomic():
        _apply_balance(wallet.id, amount)
        tx = Transaction.objects.create(
            wallet_id=wallet.id,
            tx_type=tx_type,
            amount=int(amount),
            ref=ref,
            note=note,
        )
    return tx


def wallet_sub(wallet: Wallet, amount: int, tx_type: str = "adjust", ref: str = "", note: str = "") -> Transaction:
    if amount <= 0:
        raise ValueError("amount must be > 0")

    with transaction.atomic():
        w = Wallet.objects.select_for_update().get(pk=wallet.id)
        if w.balance < amount:
            raise ValueError("insufficient balance")
        _apply_balance(wallet.id, -int(amount))
        tx = Transaction.objects.create(
            wallet_id=wallet.id,
            tx_type=tx_type,
            amount=-int(amount),
            ref=ref,
            note=note,
        )
    return tx

from django.db import models
from django.utils import timezone

# 你原本應該已經有 Wallet 了
# class Wallet(models.Model):
#     user = ...
#     balance = ...
#     ...

class WalletTx(models.Model):
    """
    錢包交易紀錄
    - shop/betting 都會用到
    """
    wallet = models.ForeignKey("accounts.Wallet", on_delete=models.CASCADE, related_name="wallet_txs")
    type = models.CharField(max_length=30, db_index=True)     # e.g. "shop_buy" / "bet_place" / "bet_payout"
    amount = models.BigIntegerField()                         # 正數入帳 / 負數扣款
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.wallet.user} {self.type} {self.amount}"
