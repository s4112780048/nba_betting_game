from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from games.models import Team, Game
from games.nba_client import fetch_schedule


class Command(BaseCommand):
    help = "Sync NBA schedule from NBA CDN (safe version: no NULL team name)"

    def _safe_str(self, v) -> str:
        return v if isinstance(v, str) and v.strip() else ""

    def _safe_team_name(self, t: dict) -> str:
        """
        保證回傳「非空字串」，避免寫入 DB 時觸發 NOT NULL constraint
        """
        name = self._safe_str(t.get("teamName"))
        city = self._safe_str(t.get("teamCity"))
        abbr = self._safe_str(t.get("teamTricode"))
        tid = t.get("teamId")

        # teamName 可能拿不到，就用 city / abbr / Team <id> 當備援
        return name or city or abbr or f"Team {tid}"

    def handle(self, *args, **options):
        data = fetch_schedule()
        league = (data or {}).get("leagueSchedule", {})
        game_dates = league.get("gameDates", [])

        created_games, updated_games = 0, 0
        created_teams, updated_teams = 0, 0
        skipped = 0

        for gd in game_dates:
            games = (gd or {}).get("games", [])
            for g in games:
                game_id = g.get("gameId")
                dt_str = g.get("gameDateTimeUTC")

                if not game_id or not dt_str:
                    skipped += 1
                    continue

                start_utc = parse_datetime(dt_str.replace("Z", "+00:00"))
                if start_utc is None:
                    skipped += 1
                    continue

                away = g.get("awayTeam") or {}
                home = g.get("homeTeam") or {}

                away_id = away.get("teamId")
                home_id = home.get("teamId")
                if not away_id or not home_id:
                    skipped += 1
                    continue

                # --- Team: away ---
                away_team, away_created = Team.objects.update_or_create(
                    nba_team_id=int(away_id),
                    defaults={
                        "name": self._safe_team_name(away),
                        "city": self._safe_str(away.get("teamCity")),
                        "abbr": self._safe_str(away.get("teamTricode")),
                    },
                )
                created_teams += int(away_created)
                updated_teams += int(not away_created)

                # --- Team: home ---
                home_team, home_created = Team.objects.update_or_create(
                    nba_team_id=int(home_id),
                    defaults={
                        "name": self._safe_team_name(home),
                        "city": self._safe_str(home.get("teamCity")),
                        "abbr": self._safe_str(home.get("teamTricode")),
                    },
                )
                created_teams += int(home_created)
                updated_teams += int(not home_created)

                # --- Game ---
                status = g.get("gameStatus", 1)
                try:
                    status = int(status)
                except Exception:
                    status = 1

                obj, is_created = Game.objects.update_or_create(
                    nba_game_id=str(game_id),
                    defaults={
                        "start_time_utc": start_utc,
                        "home_team": home_team,
                        "away_team": away_team,
                        "status": status,
                    },
                )
                created_games += int(is_created)
                updated_games += int(not is_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Schedule synced. "
                f"teams(created={created_teams}, updated={updated_teams}) "
                f"games(created={created_games}, updated={updated_games}) "
                f"skipped={skipped}"
            )
        )
