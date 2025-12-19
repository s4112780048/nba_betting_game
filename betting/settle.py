from django.db import transaction
from django.utils import timezone

from accounts.models import Wallet, WalletTx
from games.models import Game
from .models import Bet


def settle_finished_games(limit_games: int = 200):
    """
    找出已結束(status=3) 的比賽，把還在 PENDING 的下注結算：
    - 押中：payout = stake * 2（含本金），錢包 +payout
    - 押錯：payout = 0
    """
    finished_games = (
        Game.objects.select_related("winner")
        .filter(status=3)
        .order_by("-start_time_utc")[:limit_games]
    )

    settled_bets = 0
    won = 0
    lost = 0

    for g in finished_games:
        if not g.winner_id:
            # 若你有「和局/取消」狀況可改成 VOID
            continue

        bets = Bet.objects.select_related("user").filter(game=g, status=Bet.Status.PENDING)
        for b in bets:
            with transaction.atomic():
                b = Bet.objects.select_for_update().get(pk=b.pk)

                if b.status != Bet.Status.PENDING:
                    continue

                if b.pick_team_id == g.winner_id:
                    payout = b.stake * 2  # 簡單版：固定 2 倍
                    wallet, _ = Wallet.objects.select_for_update().get_or_create(user=b.user, defaults={"balance": 0})
                    wallet.balance += payout
                    wallet.save(update_fields=["balance"])
                    WalletTx.objects.create(wallet=wallet, type="bet_win", amount=payout, note=f"Win bet={b.id}")

                    b.status = Bet.Status.WON
                    b.payout = payout
                    b.settled_at = timezone.now()
                    b.save(update_fields=["status", "payout", "settled_at"])
                    won += 1
                else:
                    b.status = Bet.Status.LOST
                    b.payout = 0
                    b.settled_at = timezone.now()
                    b.save(update_fields=["status", "payout", "settled_at"])
                    lost += 1

                settled_bets += 1

    return {"settled_bets": settled_bets, "won": won, "lost": lost}
