# betting/management/commands/settle_bets.py
from django.core.management.base import BaseCommand

from betting.settle import settle_finished_games


class Command(BaseCommand):
    help = "Settle open bets for finished (final) games and update wallet + monthly leaderboard."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200, help="How many finished games to scan (default 200).")

    def handle(self, *args, **options):
        limit_games = options["limit"]
        res = settle_finished_games(limit_games=limit_games)
        self.stdout.write(self.style.SUCCESS(f"Done. {res}"))
