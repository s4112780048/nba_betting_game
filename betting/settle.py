# betting/settle.py
from __future__ import annotations

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from accounts.models import Wallet
from games.models import Game
from leaderboard.models import MonthlyScore, current_month_str
from .models import Bet


def _create_tx(wallet: Wallet, amount: int, kind: str, note: str = ""):
    """
    ✅ 自動對應 accounts.Transaction 欄位名稱（避免你遇到 Transaction() got unexpected keyword 'type'）
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
        raise RuntimeError("accounts.Transaction 找不到 wallet 欄位")

    # amount 欄位名可能不同
    if "amount" in field_names:
        kwargs["amount"] = amount
    elif "delta" in field_names:
        kwargs["delta"] = amount
    elif "value" in field_names:
        kwargs["value"] = amount
    else:
        raise RuntimeError("accounts.Transaction 找不到金額欄位（amount/delta/value 都沒有）")

    # kind/type 欄位可能不同（沒有也沒關係）
    if "type" in field_names:
        kwargs["type"] = kind
    elif "tx_type" in field_names:
        kwargs["tx_type"] = kind
    elif "kind" in field_names:
        kwargs["kind"] = kind
    elif "category" in field_names:
        kwargs["category"] = kind

    # note 欄位可能不同（沒有也沒關係）
    if note:
        if "note" in field_names:
            kwargs["note"] = note
        elif "memo" in field_names:
            kwargs["memo"] = note
        elif "description" in field_names:
            kwargs["description"] = note

    Tx.objects.create(**kwargs)


def _winner_pick_from_scores(g: Game) -> str | None:
    """
    回傳 'home' / 'away' / 'void'
    """
    if g.home_score is None or g.away_score is None:
        return "void"

    if g.home_score > g.away_score:
        return "home"
    if g.away_score > g.home_score:
        return "away"
    return "void"  # 平手 or 無法判定就當 void（你也可改規則）


def settle_finished_games(limit_games: int = 200):
    """
    結算已完賽 Game.status == 'final' 的 bets(status='open')
    - win: payout = stake * odds_x100 / 100 (含本金)
    - lose: payout = 0
    - void: 退款 stake
    並同步更新：
    - Wallet balance / Transaction 紀錄
    - MonthlyScore (profit/wins/losses)
    """
    finished_games = (
        Game.objects.select_related("home_team", "away_team")
        .filter(status="final")
        .order_by("-start_time")[:limit_games]
    )

    settled_bets = 0
    won = 0
    lost = 0
    void = 0

    for g in finished_games:
        winner_pick = _winner_pick_from_scores(g)

        # 只結算 open
        bets = Bet.objects.select_related("user").filter(game=g, status="open")

        for b in bets:
            with transaction.atomic():
                b = Bet.objects.select_for_update().get(pk=b.pk)
                if b.status != "open":
                    continue

                # 錢包 lock
                wallet, _ = Wallet.objects.select_for_update().get_or_create(
                    user=b.user, defaults={"balance": 0}
                )

                if winner_pick == "void":
                    # ✅ 退款
                    wallet.balance += b.stake
                    wallet.save(update_fields=["balance"])
                    _create_tx(wallet, amount=+b.stake, kind="bet_void", note=f"Void refund bet#{b.id} game#{g.id}")

                    b.status = "void"
                    b.payout = b.stake
                    b.settled_at = timezone.now()
                    b.save(update_fields=["status", "payout", "settled_at"])

                    # void 不影響 wins/losses/profit（你也可以改）
                    void += 1

                elif b.pick == winner_pick:
                    # ✅ 贏：入帳 gross payout（含本金）
                    gross = (b.stake * b.odds_x100) // 100
                    wallet.balance += gross
                    wallet.save(update_fields=["balance"])
                    _create_tx(wallet, amount=+gross, kind="bet_win", note=f"Win bet#{b.id} game#{g.id}")

                    b.status = "won"
                    b.payout = gross
                    b.settled_at = timezone.now()
                    b.save(update_fields=["status", "payout", "settled_at"])

                    # ✅ 排行榜：profit 記「淨利」
                    month = current_month_str(timezone.localdate())
                    ms, _ = MonthlyScore.objects.select_for_update().get_or_create(
                        user=b.user,
                        month=month,
                        defaults={"wins": 0, "losses": 0, "profit": 0, "volume": 0},
                    )
                    ms.wins += 1
                    ms.profit += (gross - b.stake)
                    ms.save(update_fields=["wins", "profit", "updated_at"])

                    won += 1

                else:
                    # ✅ 輸：不入帳
                    b.status = "lost"
                    b.payout = 0
                    b.settled_at = timezone.now()
                    b.save(update_fields=["status", "payout", "settled_at"])

                    month = current_month_str(timezone.localdate())
                    ms, _ = MonthlyScore.objects.select_for_update().get_or_create(
                        user=b.user,
                        month=month,
                        defaults={"wins": 0, "losses": 0, "profit": 0, "volume": 0},
                    )
                    ms.losses += 1
                    ms.profit -= b.stake
                    ms.save(update_fields=["losses", "profit", "updated_at"])

                    lost += 1

                settled_bets += 1

    return {"settled_bets": settled_bets, "won": won, "lost": lost, "void": void}
