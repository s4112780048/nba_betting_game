# betting/services.py
from __future__ import annotations

from typing import Optional, Literal

from django.db import transaction
from django.utils import timezone

from accounts.models import get_or_create_wallet, wallet_add, wallet_sub
from games.models import Game
from .models import Bet


Pick = Literal["home", "away"]


def place_bet(
    *,
    user,
    game_id: int,
    pick: Pick,
    stake: int,
    odds_x100: int = 200,
) -> Bet:
    """
    建立下注 + 扣款（原子性）
    - stake: int > 0
    - odds_x100: 例如 1.91 -> 191
    - idempotent: 用 bet.id 當 ref，重跑不會重複扣款
    """
    if stake <= 0:
        raise ValueError("stake must be > 0")
    if odds_x100 <= 100:
        raise ValueError("odds_x100 must be > 100 (decimal odds > 1.00)")
    if pick not in ("home", "away"):
        raise ValueError("pick must be 'home' or 'away'")

    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game_id)

        # 可自行加規則：只允許 pre/in 才能下注
        status = getattr(game, "status", "")
        if status in ("post", "final", "finished"):
            raise ValueError("Game already finished; cannot place bet.")

        bet = Bet.objects.create(
            user=user,
            game=game,
            pick=pick,
            stake=stake,
            odds_x100=odds_x100,
            status="open",
            payout=0,
        )

        wallet = get_or_create_wallet(user)
        # 扣款：ref 用 bet.id，確保重跑不會重複扣
        wallet_sub(
            wallet,
            stake,
            tx_type="bet_place",
            ref=f"bet:{bet.id}",
            note=f"Place bet #{bet.id} on game #{game.id}",
        )
        return bet


def _is_game_final(game: Game) -> bool:
    # 兼容你不同版本的 Game 欄位
    if hasattr(game, "is_final"):
        return bool(getattr(game, "is_final"))
    status = (getattr(game, "status", "") or "").lower()
    return status in ("post", "final", "finished")


def _is_game_settled(game: Game) -> bool:
    if hasattr(game, "settled"):
        return bool(getattr(game, "settled"))
    if hasattr(game, "settled_at"):
        return getattr(game, "settled_at") is not None
    return False


def _mark_game_settled(game: Game):
    now = timezone.now()
    if hasattr(game, "settled"):
        setattr(game, "settled", True)
    if hasattr(game, "settled_at"):
        setattr(game, "settled_at", now)


def _compute_winner_pick(game: Game) -> Optional[Pick]:
    """
    回傳 'home' / 'away'，或 None 表示無法判定（平手/缺分數 -> void）
    """
    home_score = getattr(game, "home_score", None)
    away_score = getattr(game, "away_score", None)
    if home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return None  # tie -> void


def settle_game(*, game_id: int) -> dict:
    """
    結算單場比賽：
    - 僅結算 open bets
    - 可重跑：不會重複入帳、也不會把已結算 bet 再動一次
    - 會把 Game 標記為 settled（若有欄位）
    """
    with transaction.atomic():
        game = Game.objects.select_for_update().get(pk=game_id)

        if not _is_game_final(game):
            return {"ok": False, "reason": "game_not_final", "game_id": game_id}

        # 若已 settled，直接返回（仍可安全重跑）
        if _is_game_settled(game):
            return {"ok": True, "reason": "already_settled", "game_id": game_id}

        winner_pick = _compute_winner_pick(game)

        # 把 open bets 全部拉出來鎖住
        bets = list(
            Bet.objects.select_for_update()
            .filter(game_id=game_id, status="open")
            .select_related("user")
        )

        now = timezone.now()
        settled_count = 0
        won_count = 0
        lost_count = 0
        void_count = 0

        for bet in bets:
            wallet = get_or_create_wallet(bet.user)

            if winner_pick is None:
                # void：退回 stake
                bet.status = "void"
                bet.payout = bet.stake
                bet.settled_at = now
                bet.save(update_fields=["status", "payout", "settled_at"])

                wallet_add(
                    wallet,
                    bet.stake,
                    tx_type="bet_refund",
                    ref=f"bet:{bet.id}",
                    note=f"Refund bet #{bet.id} (void) game #{game_id}",
                )
                void_count += 1
                settled_count += 1
                continue

            if bet.pick == winner_pick:
                payout = bet.potential_payout()
                bet.status = "won"
                bet.payout = payout
                bet.settled_at = now
                bet.save(update_fields=["status", "payout", "settled_at"])

                wallet_add(
                    wallet,
                    payout,
                    tx_type="bet_win",
                    ref=f"bet:{bet.id}",
                    note=f"Win bet #{bet.id} game #{game_id}",
                )
                won_count += 1
            else:
                bet.status = "lost"
                bet.payout = 0
                bet.settled_at = now
                bet.save(update_fields=["status", "payout", "settled_at"])
                lost_count += 1

            settled_count += 1

        # 標記 game 已結算（若有欄位）
        _mark_game_settled(game)
        # 若你 Game 有 winner 欄位也想寫，可以在這裡補（但先不要硬寫避免欄位不一致）
        game.save()

        return {
            "ok": True,
            "game_id": game_id,
            "winner_pick": winner_pick,
            "settled_bets": settled_count,
            "won": won_count,
            "lost": lost_count,
            "void": void_count,
        }
