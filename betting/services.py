# betting/services.py
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from accounts.models import get_or_create_wallet, wallet_add, wallet_sub
from betting.models import Bet
from games.models import Game


def place_bet(*, user, game_id: int, pick: str, stake: int, odds_x100: int = 200) -> Bet:
    if pick not in ("home", "away"):
        raise ValueError("pick must be 'home' or 'away'")
    if stake <= 0:
        raise ValueError("stake must be > 0")

    with transaction.atomic():
        game = Game.objects.select_for_update().get(id=game_id)
        if game.status in ("final", "canceled", "postponed"):
            raise ValueError("game is not open for betting")

        wallet = get_or_create_wallet(user)
        # 先扣款
        wallet_sub(wallet, stake, tx_type="bet_place", ref=f"game:{game.id}", note=f"pick={pick}")

        bet = Bet.objects.create(
            user=user,
            game=game,
            pick=pick,
            stake=stake,
            odds_x100=odds_x100,
            status="open",
        )
    return bet


def settle_game(*, game_id: int) -> Game:
    """
    結算單場：Game.status 必須是 final
    - 贏：發 stake * odds
    - 輸：不發
    - 平手：退回 stake（void）
    """
    with transaction.atomic():
        game = Game.objects.select_for_update().get(id=game_id)

        if game.settlement_status != "pending":
            return game

        if game.status != "final":
            return game

        winner = game.winner  # "home"/"away"/"draw"/""
        bets = Bet.objects.select_for_update().filter(game_id=game.id, status="open")

        for bet in bets:
            wallet = get_or_create_wallet(bet.user)

            if winner == "draw" or winner == "":
                # 退回 stake
                wallet_add(wallet, bet.stake, tx_type="bet_refund", ref=str(bet.id), note="draw/refund")
                bet.status = "void"
                bet.payout = bet.stake
            elif winner == bet.pick:
                payout = (bet.stake * bet.odds_x100) // 100
                wallet_add(wallet, payout, tx_type="bet_win", ref=str(bet.id), note="win payout")
                bet.status = "won"
                bet.payout = payout
            else:
                bet.status = "lost"
                bet.payout = 0

            bet.settled_at = timezone.now()
            bet.save(update_fields=["status", "payout", "settled_at"])

        game.settlement_status = "settled"
        game.settled_at = timezone.now()
        game.save(update_fields=["settlement_status", "settled_at"])
        return game
