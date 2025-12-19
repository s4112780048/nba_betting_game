# betting/services.py
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from accounts.models import Wallet, WalletTx
from games.models import Game, Team
from .models import Bet

from leaderboard.models import MonthlyScore, current_month_str


def _get_wallet_for_update(user):
    w, _ = Wallet.objects.select_for_update().get_or_create(user=user, defaults={"balance": 0})
    return w


def place_bet(user, game: Game, pick_team: Team, stake: int):
    if stake <= 0:
        raise ValidationError("stake 必須 > 0")

    now = timezone.now()
    if game.status != 1:
        raise ValidationError("此場比賽不是 Scheduled，不能下注")
    if game.start_time_utc <= now:
        raise ValidationError("比賽已開始/已過開賽時間，不能下注")

    if pick_team_id := getattr(pick_team, "id", None):
        if pick_team_id not in (game.home_team_id, game.away_team_id):
            raise ValidationError("下注隊伍不在此場比賽")

    with transaction.atomic():
        w = _get_wallet_for_update(user)

        if w.balance < stake:
            raise ValidationError("餘額不足")

        # 防重複下注：同一場每人只能一張
        if Bet.objects.select_for_update().filter(user=user, game=game).exists():
            raise ValidationError("你已經下注過這一場了")

        w.balance -= stake
        w.save(update_fields=["balance"])

        WalletTx.objects.create(
            wallet=w, type="bet_stake", amount=-stake,
            note=f"Bet stake game={game.id} pick={pick_team.abbr}"
        )

        Bet.objects.create(user=user, game=game, pick_team=pick_team, stake=stake, status="OPEN")

    return True


def settle_game_bets(game: Game) -> int:
    """
    結算單場：只跑 final + 有 winner + 尚未 settled_at
    payout 規則：1:1（贏了拿回 2*stake，其中 stake 先前已扣，所以這裡加 stake*2）
    """
    if game.status != 3 or not game.winner_id:
        return 0
    if game.settled_at is not None:
        return 0

    settled_count = 0

    with transaction.atomic():
        # 再鎖一次避免併發
        game = Game.objects.select_for_update().get(pk=game.pk)
        if game.settled_at is not None or game.status != 3 or not game.winner_id:
            return 0

        bets = Bet.objects.select_for_update().filter(game=game, status="OPEN").select_related("user", "pick_team")

        for b in bets:
            w = _get_wallet_for_update(b.user)

            win = (b.pick_team_id == game.winner_id)
            payout = b.stake * 2 if win else 0

            if payout > 0:
                w.balance += payout
                w.save(update_fields=["balance"])
                WalletTx.objects.create(
                    wallet=w, type="bet_win", amount=payout,
                    note=f"Bet win game={game.id} stake={b.stake}"
                )
            else:
                WalletTx.objects.create(
                    wallet=w, type="bet_lose", amount=0,
                    note=f"Bet lose game={game.id} stake={b.stake}"
                )

            # 更新排行榜（月）
            month = current_month_str(game.start_time_utc)
            ms, _ = MonthlyScore.objects.select_for_update().get_or_create(user=b.user, month=month)
            ms.volume += b.stake
            if win:
                ms.wins += 1
                ms.profit += (payout - b.stake)  # 淨利：贏=+stake（因為 stake 先扣了）
            else:
                ms.losses += 1
                ms.profit -= b.stake
            ms.save()

            b.status = "SETTLED"
            b.payout = payout
            b.settled_at = timezone.now()
            b.save(update_fields=["status", "payout", "settled_at"])
            settled_count += 1

        game.settled_at = timezone.now()
        game.save(update_fields=["settled_at"])

    return settled_count
