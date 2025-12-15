from django.core.management.base import BaseCommand
from django.utils import timezone
from games.models import Game
from games.nba_client import fetch_today_scoreboard
from betting.services import settle_game_if_final

class Command(BaseCommand):
    help = "Sync today's scoreboard and settle bets"

    def handle(self, *args, **options):
        data = fetch_today_scoreboard()
        games = data.get("scoreboard", {}).get("games", [])

        touched = 0
        for g in games:
            game_id = g.get("gameId")
            if not game_id:
                continue

            try:
                obj = Game.objects.select_related("home_team", "away_team").get(nba_game_id=game_id)
            except Game.DoesNotExist:
                continue

            obj.status = int(g.get("gameStatus", obj.status))
            obj.home_score = int(g.get("homeTeam", {}).get("score", obj.home_score))
            obj.away_score = int(g.get("awayTeam", {}).get("score", obj.away_score))

            if obj.status == 3:
                if obj.home_score > obj.away_score:
                    obj.winner = obj.home_team
                elif obj.away_score > obj.home_score:
                    obj.winner = obj.away_team

            obj.save()
            touched += 1

            if obj.status == 3 and obj.winner_id:
                settle_game_if_final(obj)

        self.stdout.write(self.style.SUCCESS(f"Today synced. touched={touched}"))
