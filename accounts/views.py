from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .models import Wallet

def signup_view(request):
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("core:home")
    return render(request, "accounts/signup.html", {"form": form})

def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("core:home")
    return render(request, "accounts/login.html", {"form": form})

def logout_view(request):
    logout(request)
    return redirect("core:home")

@login_required
def wallet_view(request):
    wallet = Wallet.objects.get(user=request.user)
    txs = wallet.txs.all()[:50]
    return render(request, "accounts/wallet.html", {"wallet": wallet, "txs": txs})
