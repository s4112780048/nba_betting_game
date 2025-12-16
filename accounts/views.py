from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db import IntegrityError
from .models import Wallet

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.utils import OperationalError
from django.shortcuts import render, redirect

from .models import Wallet, WalletTx


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        password2 = request.POST.get("password2") or ""

        if not username:
            return render(request, "accounts/signup.html", {"error": "請輸入帳號"})
        if len(password) < 6:
            return render(request, "accounts/signup.html", {"error": "密碼至少 6 碼"})
        if password != password2:
            return render(request, "accounts/signup.html", {"error": "兩次密碼不一致"})

        try:
            with transaction.atomic():
                user = User.objects.create_user(username=username, password=password)

                # ✅ 註冊就直接建錢包（避免 signals 沒載入或資料表問題）
                w, created = Wallet.objects.get_or_create(user=user, defaults={"balance": 1000})
                if created:
                    WalletTx.objects.create(wallet=w, type="init", amount=1000, note="Initial coins")

        except IntegrityError:
            return render(request, "accounts/signup.html", {"error": "這個帳號已被使用"})
        except OperationalError:
            return render(request, "accounts/signup.html", {"error": "資料表尚未建立，請先執行：python manage.py migrate"})
        except Exception as e:
            return render(request, "accounts/signup.html", {"error": f"註冊失敗：{e}"})

        login(request, user)
        messages.success(request, "✅ 註冊成功！已自動登入，並獲得 1000 初始金幣。")
        return redirect("core:home")

    return render(request, "accounts/signup.html")


def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("core:home")
    return render(request, "accounts/login.html", {"form": form})

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        password2 = request.POST.get("password2") or ""

        if not username:
            return render(request, "accounts/signup.html", {"error": "請輸入帳號"})
        if len(password) < 6:
            return render(request, "accounts/signup.html", {"error": "密碼至少 6 碼"})
        if password != password2:
            return render(request, "accounts/signup.html", {"error": "兩次密碼不一致"})

        try:
            user = User.objects.create_user(username=username, password=password)
        except IntegrityError:
            return render(request, "accounts/signup.html", {"error": "這個帳號已被使用"})
        except Exception as e:
            return render(request, "accounts/signup.html", {"error": f"註冊失敗：{e}"})

        # ✅ 註冊完自動登入
        login(request, user)

        messages.success(request, "✅ 註冊成功！已自動登入。")
        return redirect("core:home")

    return render(request, "accounts/signup.html")


def logout_view(request):
    logout(request)
    return redirect("core:home")

@login_required
def wallet_view(request):
    wallet = Wallet.objects.get(user=request.user)
    txs = wallet.txs.all()[:50]
    return render(request, "accounts/wallet.html", {"wallet": wallet, "txs": txs})

from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone

from .models import DailyCheckin, Wallet, WalletTx

@login_required
def daily_bonus(request):
    today = timezone.localdate()

    with transaction.atomic():
        chk, _ = DailyCheckin.objects.select_for_update().get_or_create(user=request.user)

        if chk.last_claim_date == today:
            messages.info(request, "今天已經領過每日簽到了。")
            return redirect("core:home")

        # 計算連續天數
        if chk.last_claim_date == today - timedelta(days=1):
            chk.streak += 1
        else:
            chk.streak = 1

        chk.last_claim_date = today
        chk.save()

        # 獎勵：100 起跳，每連續一天 +20，上限 300
        bonus = min(100 + (chk.streak - 1) * 20, 300)

        w, _ = Wallet.objects.get_or_create(user=request.user, defaults={"balance": 0})
        w.balance += bonus
        w.save()

        WalletTx.objects.create(wallet=w, type="daily_bonus", amount=bonus, note=f"Daily bonus streak={chk.streak}")

    messages.success(request, f"✅ 簽到成功！獲得 {bonus} 金幣（連續 {chk.streak} 天）")
    return redirect("accounts:wallet")
