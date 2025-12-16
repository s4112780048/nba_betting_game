from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import DailyCheckin, Wallet, WalletTx


def login_view(request):
    """
    ✅ 只留 Google 登入：這頁只顯示 Google 登入按鈕
    Google 的實際 OAuth 路由走 allauth（在 /auth/ 底下）
    """
    if request.user.is_authenticated:
        return redirect("core:home")

    next_url = request.GET.get("next") or ""
    return render(request, "accounts/login.html", {"next": next_url})


def logout_view(request):
    logout(request)
    return redirect("core:home")


@login_required
def wallet_view(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user, defaults={"balance": 1000})
    txs = wallet.txs.all().order_by("-id")[:50]
    return render(request, "accounts/wallet.html", {"wallet": wallet, "txs": txs})


@login_required
def daily_bonus(request):
    today = timezone.localdate()

    with transaction.atomic():
        chk, _ = DailyCheckin.objects.select_for_update().get_or_create(user=request.user)

        if chk.last_claim_date == today:
            messages.info(request, "今天已經領過每日簽到了。")
            return redirect("accounts:wallet")

        if chk.last_claim_date == today - timedelta(days=1):
            chk.streak += 1
        else:
            chk.streak = 1

        chk.last_claim_date = today
        chk.save()

        bonus = min(100 + (chk.streak - 1) * 20, 300)

        w, _ = Wallet.objects.get_or_create(user=request.user, defaults={"balance": 1000})
        w.balance += bonus
        w.save()

        WalletTx.objects.create(wallet=w, type="daily_bonus", amount=bonus, note=f"Daily bonus streak={chk.streak}")

    messages.success(request, f"✅ 簽到成功！獲得 {bonus} 金幣（連續 {chk.streak} 天）")
    return redirect("accounts:wallet")
