import random
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect

from accounts.models import Wallet, WalletTx
from .models import ShopItem, InventoryItem, Badge, UserBadge, LootOpenLog


def shop_list(request):
    items = ShopItem.objects.filter(active=True).order_by("price", "code")
    return render(request, "shop/list.html", {"items": items})


@login_required
@transaction.atomic
def buy_item(request, item_id):
    if request.method != "POST":
        return redirect("shop:list")

    item = get_object_or_404(ShopItem, pk=item_id, active=True)

    w, _ = Wallet.objects.select_for_update().get_or_create(user=request.user, defaults={"balance": 0})
    if w.balance < item.price:
        messages.error(request, "餘額不足，無法購買。")
        return redirect("shop:list")

    # 扣款
    w.balance -= item.price
    w.save()
    WalletTx.objects.create(wallet=w, type="shop_buy", amount=-item.price, note=f"Buy {item.code}")

    # 發放物品
    if item.kind == "BADGE":
        badge_code = (item.payload or {}).get("badge_code")
        badge = Badge.objects.filter(code=badge_code).first()
        if not badge:
            messages.error(request, "這個徽章商品設定有問題（找不到 badge_code）。")
            return redirect("shop:list")

        UserBadge.objects.get_or_create(user=request.user, badge=badge)
        messages.success(request, f"✅ 已獲得徽章：{badge.emoji} {badge.name}")
        return redirect("shop:inventory")

    inv, _ = InventoryItem.objects.get_or_create(user=request.user, item=item, defaults={"qty": 0})
    inv.qty += 1
    inv.save()

    if item.kind == "LOOT_BOX":
        messages.success(request, "✅ 已購買戰利品箱，去背包開箱吧！")
    else:
        messages.success(request, f"✅ 已購買：{item.name}")
    return redirect("shop:inventory")


@login_required
def inventory(request):
    inv_items = (
        InventoryItem.objects.select_related("item")
        .filter(user=request.user, qty__gt=0)
        .order_by("item__kind", "item__price")
    )
    badges = (
        UserBadge.objects.select_related("badge")
        .filter(user=request.user)
        .order_by("-equipped", "-badge__rarity", "badge__name")
    )
    return render(request, "shop/inventory.html", {"inv_items": inv_items, "badges": badges})


@login_required
@transaction.atomic
def open_lootbox(request, inv_id):
    if request.method != "POST":
        return redirect("shop:inventory")

    inv = get_object_or_404(
        InventoryItem.objects.select_for_update().select_related("item"),
        pk=inv_id,
        user=request.user,
    )

    if inv.item.kind != "LOOT_BOX" or inv.qty <= 0:
        messages.error(request, "這個物品不能開箱。")
        return redirect("shop:inventory")

    inv.qty -= 1
    inv.save()

    payload = inv.item.payload or {}
    minc = int(payload.get("min_coins", 100))
    maxc = int(payload.get("max_coins", 400))
    badge_chance = float(payload.get("badge_chance", 0.35))
    badge_pool = payload.get("badge_pool", [])

    got_badge = False
    reward_badge = None
    reward_coins = 0

    # 抽徽章
    if badge_pool and random.random() < badge_chance:
        reward_badge = Badge.objects.filter(code__in=badge_pool).order_by("?").first()
        if reward_badge:
            UserBadge.objects.get_or_create(user=request.user, badge=reward_badge)
            got_badge = True

    # 沒中徽章 → 抽金幣
    if not got_badge:
        reward_coins = random.randint(minc, maxc)
        w, _ = Wallet.objects.select_for_update().get_or_create(user=request.user, defaults={"balance": 0})
        w.balance += reward_coins
        w.save()
        WalletTx.objects.create(wallet=w, type="lootbox", amount=reward_coins, note=f"Open {inv.item.code}")

    LootOpenLog.objects.create(
        user=request.user,
        source_item=inv.item,
        reward_type="badge" if got_badge else "coins",
        coins=reward_coins,
        badge=reward_badge,
    )

    if got_badge:
        messages.success(request, f"🎉 開箱獲得徽章：{reward_badge.emoji} {reward_badge.name}")
    else:
        messages.success(request, f"🎉 開箱獲得金幣：{reward_coins}")

    return redirect("shop:inventory")


@login_required
@transaction.atomic
def equip_badge(request, badge_id):
    if request.method != "POST":
        return redirect("shop:inventory")

    ub = get_object_or_404(
        UserBadge.objects.select_for_update().select_related("badge"),
        pk=badge_id,
        user=request.user,
    )

    UserBadge.objects.filter(user=request.user, equipped=True).update(equipped=False)
    ub.equipped = True
    ub.save()

    messages.success(request, f"✅ 已裝備徽章：{ub.badge.emoji} {ub.badge.name}")
    return redirect("shop:inventory")
