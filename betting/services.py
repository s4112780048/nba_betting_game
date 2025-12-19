from django.db import transaction
from django.utils import timezone

from accounts.models import Wallet, WalletTx
from games.models import Game, Team
from .models import Bet


def place_bet(user, game: Game, pick_team: Team, stake: int) -> Bet:
    stake = int(stake)
    if stake <= 0:
        raise ValueError("下注金額必須 > 0")

    # 只允許未開賽下注
    if game.status != 1:
        raise ValueError("此比賽已開賽/結束，無法下注")

    if game.start_time_utc <= timezone.now():
        raise ValueError("已超過開賽時間，無法下注")

    # pick_team 必須是主/客其中之一
    if pick_team_id := getattr(pick_team, "id", None):
        if pick_team_id not in (game.home_team_id, game.away_team_id):
            raise ValueError("下注隊伍不屬於此場比賽")
    else:
        raise ValueError("pick_team 不合法")

    with transaction.atomic():
        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user, defaults={"balance": 0})
        if wallet.balance < stake:
            raise ValueError("餘額不足")

        # 扣錢
        wallet.balance -= stake
        wallet.save(update_fields=["balance"])
        WalletTx.objects.create(wallet=wallet, type="bet_place", amount=-stake, note=f"Bet on game={game.id}")

        bet = Bet.objects.create(user=user, game=game, pick_team=pick_team, stake=stake)

    return bet
