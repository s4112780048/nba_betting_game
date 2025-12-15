from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction

from accounts.models import Wallet, wallet_add
from .models import ShopItem, Inventory

def shop_list(request):
    items = ShopItem.objects.filter(active=True).order_by("price")
    return render(request, "shop/shop_list.html", {"items": items})

@login_required
def inventory_view(request):
    inv = Inventory.objects.select_related("item").filter(user=request.user).order_by("item__price")
    return render(request, "shop/inventory.html", {"inv": inv})

@login_required
def buy_item(request, item_id):
    item = get_object_or_404(ShopItem, pk=item_id, active=True)
    wallet = Wallet.objects.get(user=request.user)

    with transaction.atomic():
        wallet_add(wallet, -item.price, "purchase", note=f"Buy {item.code}")
        inv, _ = Inventory.objects.get_or_create(user=request.user, item=item)
        inv.quantity += 1
        inv.save(update_fields=["quantity"])

    return redirect("shop:inventory")
