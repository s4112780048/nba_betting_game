from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .models import Transaction, get_or_create_wallet, wallet_add, wallet_sub


# === 兼容舊路由：/accounts/login/ /accounts/signup/ /accounts/logout/ ===
def login_view(request: HttpRequest) -> HttpResponse:
    return redirect("account_login")   # allauth


def signup_view(request: HttpRequest) -> HttpResponse:
    return redirect("account_signup")  # allauth


def logout_view(request: HttpRequest) -> HttpResponse:
    return redirect("account_logout")  # allauth


# === Wallet ===
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
        wallet_add(wallet, amount, tx_type="deposit", ref="manual")
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
        wallet_sub(wallet, amount, tx_type="withdraw", ref="manual")
        messages.success(request, f"已提領 {amount}")
    except Exception as e:
        messages.error(request, f"提領失敗：{e}")

    return redirect("accounts:wallet")
