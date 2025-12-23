# accounts/views.py
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Wallet, Transaction, get_or_create_wallet, wallet_add, wallet_sub


def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, "註冊成功，已自動登入 ✅")
            return redirect(request.POST.get("next") or "home")
    else:
        form = UserCreationForm()

    return render(request, "accounts/signup.html", {"form": form})


@login_required
def wallet_view(request: HttpRequest) -> HttpResponse:
    wallet = get_or_create_wallet(request.user)
    txs = Transaction.objects.filter(wallet=wallet).order_by("-created_at")[:50]
    return render(request, "accounts/wallet.html", {"wallet": wallet, "txs": txs})


@login_required
def deposit(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("accounts:wallet")

    try:
        amount = int(request.POST.get("amount", "0"))
        if amount <= 0:
            raise ValueError("amount must be > 0")
        wallet = get_or_create_wallet(request.user)
        wallet_add(wallet, amount, tx_type="deposit", ref="manual", note="手動儲值")
        messages.success(request, f"已儲值 {amount}")
    except Exception as e:
        messages.error(request, f"儲值失敗：{e}")

    return redirect("accounts:wallet")


@login_required
def withdraw(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("accounts:wallet")

    try:
        amount = int(request.POST.get("amount", "0"))
        if amount <= 0:
            raise ValueError("amount must be > 0")
        wallet = get_or_create_wallet(request.user)
        wallet_sub(wallet, amount, tx_type="withdraw", ref="manual", note="手動提領")
        messages.success(request, f"已提領 {amount}")
    except Exception as e:
        messages.error(request, f"提領失敗：{e}")

    return redirect("accounts:wallet")


@login_required
def daily_bonus(request: HttpRequest) -> HttpResponse:
    BONUS = 100
    today = timezone.localdate()

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(user=request.user)

        if wallet.last_checkin_date == today:
            messages.info(request, "你今天已經簽到過了 ✅")
            return redirect("accounts:wallet")

        wallet_add(
            wallet,
            BONUS,
            tx_type="daily_bonus",
            ref=f"daily_bonus:{today.isoformat()}",
            note="每日簽到",
        )
        wallet.last_checkin_date = today
        wallet.save(update_fields=["last_checkin_date"])

    messages.success(request, f"每日簽到成功！獲得 +{BONUS} 💰")
    return redirect("accounts:wallet")

from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.contrib import messages


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "🎉 註冊成功，請登入")
            return redirect("login")
    else:
        form = UserCreationForm()

    return render(request, "accounts/signup.html", {"form": form})
