import time
from datetime import timedelta

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from games.models import Team, Game


NBA_SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/scoreboard_{yyyymmdd}.json"


def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _parse_utc_iso(s: str):
    """
    NBA CDN often returns ISO like '2025-12-15T00:00:00Z'
    """
    if not s:
        return None
    try:
        # turn 'Z' into '+00:00'
        s = s.replace("Z", "+00:00")
        dt = timezone.datetime.fromisoformat(s)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


class Command(BaseCommand):
    help = "Backfill NBA games/scores/status for past N days using NBA CDN scoreboard."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14, help="How many days back to sync (default 14).")
        parser.add_argument("--sleep", type=float, default=0.15, help="Sleep seconds between requests.")
        parser.add_argument("--timeout", type=float, default=12.0, help="HTTP timeout seconds.")

    def handle(self, *args, **options):
        days = max(1, int(options["days"]))
        sleep_s = float(options["sleep"])
        timeout = float(options["timeout"])

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; NBA Betting Django; +https://example.com)",
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://www.nba.com/",
                "Origin": "https://www.nba.com",
            }
        )

        today_utc = timezone.now().astimezone(timezone.utc).date()
        start_date = today_utc - timedelta(days=days)

        created_games = 0
        updated_games = 0
        created_teams = 0
        updated_teams = 0
        skipped_days = 0
        skipped_games = 0

        self.stdout.write(f"Backfill from {start_date} to {today_utc} (UTC), days={days}")

        d = start_date
        while d <= today_utc:
            yyyymmdd = d.strftime("%Y%m%d")
            url = NBA_SCOREBOARD_URL.format(yyyymmdd=yyyymmdd)

            try:
                r = session.get(url, timeout=timeout)
                if r.status_code != 200:
                    skipped_days += 1
                    self.stdout.write(self.style.WARNING(f"[SKIP] {yyyymmdd} status={r.status_code}"))
                    d += timedelta(days=1)
                    time.sleep(sleep_s)
                    continue

                payload = r.json()
                games = (payload.get("scoreboard") or {}).get("games") or []
            except Exception as e:
                skipped_days += 1
                self.stdout.write(self.style.WARNING(f"[SKIP] {yyyymmdd} error={e}"))
                d += timedelta(days=1)
                time.sleep(sleep_s)
                continue

            for g in games:
                try:
                    game_id = str(g.get("gameId") or "").strip()
                    if not game_id:
                        skipped_games += 1
                        continue

                    status = _safe_int(g.get("gameStatus"), 1)

                    # teams
                    home = g.get("homeTeam") or {}
                    away = g.get("awayTeam") or {}

                    home_id = _safe_int(home.get("teamId"), 0)
                    away_id = _safe_int(away.get("teamId"), 0)
                    if home_id <= 0 or away_id <= 0:
                        skipped_games += 1
                        continue

                    home_abbr = (home.get("teamTricode") or "").strip()
                    away_abbr = (away.get("teamTricode") or "").strip()

                    # NOTE: avoid NOT NULL constraint
                    home_name = (home.get("teamName") or home_abbr or f"TEAM_{home_id}").strip()
                    away_name = (away.get("teamName") or away_abbr or f"TEAM_{away_id}").strip()

                    home_city = (home.get("teamCity") or "").strip()
                    away_city = (away.get("teamCity") or "").strip()

                    with transaction.atomic():
                        home_team, home_created = Team.objects.update_or_create(
                            nba_team_id=home_id,
                            defaults={"name": home_name, "city": home_city, "abbr": home_abbr},
                        )
                        away_team, away_created = Team.objects.update_or_create(
                            nba_team_id=away_id,
                            defaults={"name": away_name, "city": away_city, "abbr": away_abbr},
                        )

                        if home_created:
                            created_teams += 1
                        else:
                            updated_teams += 1
                        if away_created:
                            created_teams += 1
                        else:
                            updated_teams += 1

                        # time
                        start_time = _parse_utc_iso(g.get("gameTimeUTC") or "")
                        if start_time is None:
                            # fallback: date noon UTC to avoid crashing
                            start_time = timezone.make_aware(
                                timezone.datetime(d.year, d.month, d.day, 12, 0, 0),
                                timezone=timezone.utc,
                            )

                        home_score = _safe_int(home.get("score"), 0)
                        away_score = _safe_int(away.get("score"), 0)

                        winner = None
                        if status == 3:  # final
                            if home_score > away_score:
                                winner = home_team
                            elif away_score > home_score:
                                winner = away_team

                        obj, created = Game.objects.update_or_create(
                            nba_game_id=game_id,
                            defaults={
                                "start_time_utc": start_time,
                                "status": status,
                                "home_team": home_team,
                                "away_team": away_team,
                                "home_score": home_score,
                                "away_score": away_score,
                                "winner": winner,
                            },
                        )
                        if created:
                            created_games += 1
                        else:
                            updated_games += 1

                except Exception:
                    skipped_games += 1
                    continue

            self.stdout.write(f"[OK] {yyyymmdd} games={len(games)}")
            d += timedelta(days=1)
            time.sleep(sleep_s)

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill done. teams(created={created_teams}, updated={updated_teams}) "
                f"games(created={created_games}, updated={updated_games}) "
                f"skipped_days={skipped_days} skipped_games={skipped_games}"
            )
        )
