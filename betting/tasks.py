# betting/tasks.py
from celery import shared_task
from games.models import Game
from .models import Bet
from .services import settle_bet


@shared_task
def settle_finished_games() -> dict:
    """
    1) 找出 final 且尚未 settled 的 games
    2) 結算該場所有 open bets
    """
    result = {"games_checked": 0, "bets_settled": 0}

    games = Game.objects.filter(status="final", settlement_status="pending").order_by("start_time")[:200]
    for g in games:
        result["games_checked"] += 1

        open_bet_ids = Bet.objects.filter(game=g, status="open").values_list("id", flat=True)
        for bet_id in open_bet_ids:
            settle_bet(Bet(id=bet_id))
            result["bets_settled"] += 1

        g.mark_settled()
        g.save(update_fields=["settlement_status", "settled_at"])

    return result
