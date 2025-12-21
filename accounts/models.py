# accounts/models.py
from __future__ import annotations

import uuid
from typing import Optional

from django.conf import settings
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    balance = models.BigIntegerField(default=0)  # 用整數避免浮點
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
        ("adjust", "Adjust"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="txs")
    tx_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.BigIntegerField()  # +收入 / -支出
    ref = models.CharField(max_length=128, blank=True, default="")  # e.g. bet_id / game_id
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["wallet", "created_at"])]

    def __str__(self):
        return f"{self.tx_type} {self.amount} ({self.wallet.user})"


def get_or_create_wallet(user) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def apply_balance(wallet: Wallet, amount: int):
    """
    原子性更新餘額（避免併發結算重複加錢）
    """
    Wallet.objects.filter(pk=wallet.pk).update(balance=F("balance") + amount)


def _tx_exists(wallet_id: int, tx_type: str, ref: str) -> bool:
    if not ref:
        return False
    return Transaction.objects.filter(wallet_id=wallet_id, tx_type=tx_type, ref=ref).exists()


def wallet_add(
    wallet: Wallet,
    amount: int,
    *,
    tx_type: str = "deposit",
    ref: str = "",
    note: str = "",
) -> Optional[Transaction]:
    """
    入帳：amount 必須為正整數
    - 若提供 ref，會做 idempotent：同 wallet/tx_type/ref 已存在就不重複入帳
    """
    if amount <= 0:
        raise ValueError("wallet_add amount must be > 0")

    with transaction.atomic():
        w = Wallet.objects.select_for_update().get(pk=wallet.pk)

        if _tx_exists(w.id, tx_type, ref):
            return None

        apply_balance(w, amount)
        tx = Transaction.objects.create(wallet=w, tx_type=tx_type, amount=amount, ref=ref, note=note)
        return tx


def wallet_sub(
    wallet: Wallet,
    amount: int,
    *,
    tx_type: str = "withdraw",
    ref: str = "",
    note: str = "",
    allow_negative: bool = False,
) -> Optional[Transaction]:
    """
    扣款：amount 必須為正整數（內部會記錄成負數）
    - 若提供 ref，會做 idempotent：同 wallet/tx_type/ref 已存在就不重複扣款
    - 預設不允許餘額變負（allow_negative=False）
    """
    if amount <= 0:
        raise ValueError("wallet_sub amount must be > 0")

    with transaction.atomic():
        w = Wallet.objects.select_for_update().get(pk=wallet.pk)

        if _tx_exists(w.id, tx_type, ref):
            return None

        if (not allow_negative) and w.balance < amount:
            raise ValueError(f"Insufficient balance: have={w.balance}, need={amount}")

        apply_balance(w, -amount)
        tx = Transaction.objects.create(wallet=w, tx_type=tx_type, amount=-amount, ref=ref, note=note)
        return tx


# ✅ 相容舊程式：以前有人 import WalletTx
WalletTx = Transaction
