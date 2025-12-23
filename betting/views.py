# betting/views.py
from __future__ import annotations

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

from accounts.models import Wallet
from games.models import Game
from leaderboard.models import MonthlyScore, current_month_str
from .models import Bet


def _create_tx(wallet: Wallet, amount: int, kind: str, note: str = ""):
    """
    ✅ 自動對應 accounts.Transaction 欄位名稱，不再硬寫 type / note
    - kind 可能叫 type / tx_type / kind / category...
    - note 可能叫 note / memo / description...
    """
    Tx = apps.get_model("accounts", "Transaction")
    field_names = {f.name for f in Tx._meta.get_fields() if getattr(f, "concrete", False)}

    kwargs = {}

    # wallet FK
    if "wallet" in field_names:
        kwargs["wallet"] = wallet
    elif "wallet_id" in field_names:
        kwargs["wallet_id"] = wallet.id
    else:
        # 真的很少見，但保險
        raise RuntimeError("accounts.Transaction 找不到 wallet 欄位")

    # amount
    if "amount" in field_names:
        kwargs["amount"] = amount
    elif "delta" in field_names:
        kwargs["delta"] = amount
    elif "value" in field_names:
        kwargs["value"] = amount
    else:
        raise RuntimeError("accounts.Transaction 找不到金額欄位（amount/delta/value 都沒有）")

    # kind/type
    if "type" in field_names:
        kwargs["type"] = kind
    elif "tx_type" in field_names:
        kwargs["tx_type"] = kind
    elif "kind" in field_names:
        kwargs["kind"] = kind
    elif "category" in field_names:
        kwargs["category"] = kind
    # 沒有也沒關係：至少金額紀錄還是會進去

    # note/memo
    if note:
        if "note" in field_names:
            kwargs["note"] = note
        elif "memo" in field_names:
            kwargs["memo"] = note
        elif "description" in field_names:
            kwargs["description"] = note

    Tx.objects.create(**kwargs)


@login_required
@transaction.atomic
def place_bet(request, game_id: int):
    if request.method != "POST":
        return redirect("games:detail", game_id=game_id)

    game = get_object_or_404(Game, pk=game_id)

    # 只允許 scheduled / in_progress
    if game.status not in ("scheduled", "in_progress"):
        messages.error(request, "這場比賽目前不可下注。")
        return redirect("games:detail", game_id=game_id)

    pick = (request.POST.get("pick") or "").strip()  # "home" / "away"
    stake_raw = request.POST.get("stake")

    if pick not in ("home", "away"):
        messages.error(request, "請選擇主勝或客勝。")
        return redirect("games:detail", game_id=game_id)

    try:
        stake = int(stake_raw)
    except Exception:
        stake = 0

    if stake <= 0:
        messages.error(request, "下注金額必須大於 0。")
        return redirect("games:detail", game_id=game_id)

    # 錢包扣款
    w, _ = Wallet.objects.select_for_update().get_or_create(user=request.user, defaults={"balance": 0})
    if w.balance < stake:
        messages.error(request, "餘額不足。")
        return redirect("games:detail", game_id=game_id)

    w.balance -= stake
    w.save(update_fields=["balance"])

    # ✅ 交易紀錄（自動對應欄位）
    _create_tx(
        wallet=w,
        amount=-stake,
        kind="bet",
        note=f"Bet game#{game.id} pick={pick}",
    )

    # 建立 Bet
    Bet.objects.create(
        user=request.user,
        game=game,
        pick=pick,
        stake=stake,
        odds_x100=200,   # 先固定，之後你要做賠率再改
        status="open",
        payout=0,
        created_at=timezone.now(),
    )

    # ✅ 排行榜：下注當下先更新「volume」（交易量）
    month = current_month_str()
    ms, _ = MonthlyScore.objects.select_for_update().get_or_create(
        user=request.user,
        month=month,
        defaults={"wins": 0, "losses": 0, "profit": 0, "volume": 0},
    )
    ms.volume += stake
    ms.save(update_fields=["volume", "updated_at"])

    messages.success(request, "✅ 下注成功！")
    return redirect("games:detail", game_id=game_id)
