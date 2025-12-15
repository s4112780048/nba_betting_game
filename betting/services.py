from django.db import transaction
from django.utils import timezone

from accounts.models import Wallet, wallet_add
from .models import Bet, MonthlyScore

def _month_key(dt):
    local = timezone.localtime(dt)
    return local.year, local.month

def place_bet(user, game, pick_team, stake: int):
    if stake <= 0:
        raise ValueError("stake must be > 0")
    if timezone.now() >= game.start_time_utc:
        raise ValueError("Game already started")

    wallet = Wallet.objects.get(user=user)

    with transaction.atomic():
        wallet_add(wallet, -stake, "bet", note=f"Bet {stake} on {pick_team} (game {game.nba_game_id})")
        bet = Bet.objects.create(user=user, game=game, pick_team=pick_team, stake=stake)
    return bet

def settle_game_if_final(game):
    if game.status != 3 or not game.winner_id:
        return

    bets = Bet.objects.select_for_update().filter(game=game, status=Bet.Status.PENDING).select_related("user")

    if not bets.exists():
        return

    with transaction.atomic():
        for bet in bets:
            win = (bet.pick_team_id == game.winner_id)

            base_points = 10 + bet.stake // 10

            if win:
                payout = bet.stake * 2  # 簡化：贏就 2 倍返還（含本金）
                wallet_add(Wallet.objects.get(user=bet.user), payout, "payout",
                           note=f"Win bet (game {game.nba_game_id})")
                bet.status = Bet.Status.WON
                bet.payout = payout
                bet.points = base_points
            else:
                bet.status = Bet.Status.LOST
                bet.payout = 0
                bet.points = max(1, base_points // 4)

            bet.save(update_fields=["status", "payout", "points"])

            y, m = _month_key(bet.placed_at)
            ms, _ = MonthlyScore.objects.get_or_create(user=bet.user, year=y, month=m)
            ms.points += bet.points
            ms.save(update_fields=["points"])
