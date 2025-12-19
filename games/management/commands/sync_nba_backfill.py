import time
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from games.models import Team, Game

# ✅ 改用 data.nba.net（雲端通常不會 403）
DATA_NBA_SCOREBOARD_URL = "https://data.nba.net/10s/prod/v1/{yyyymmdd}/scoreboard.json"


def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _parse_utc_iso(s: str):
    # 例如 "2025-12-15T00:00:00.000Z"
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        return dt.astimezone(dt_timezone.utc)
    except Exception:
        return None


class Command(BaseCommand):
    help = "Backfill NBA games/scores/status for past N days using data.nba.net scoreboard."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14, help="How many days back to sync (default 14).")
        parser.add_argument("--sleep", type=float, default=0.2, help="Sleep seconds between requests.")
        parser.add_argument("--timeout", type=float, default=12.0, help="HTTP timeout seconds.")
        parser.add_argument("--quiet", action="store_true", help="Less per-day logs.")

    def handle(self, *args, **options):
        days = max(1, int(options["days"]))
        sleep_s = max(0.0, float(options["sleep"]))
        timeout = float(options["timeout"])
        quiet = bool(options["quiet"])

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; NBA Betting Django)",
                "Accept": "application/json,text/plain,*/*",
            }
        )

        today_utc = timezone.now().astimezone(dt_timezone.utc).date()
        start_date = today_utc - timedelta(days=days)

        created_games = updated_games = 0
        created_teams = updated_teams = 0
        skipped_days = skipped_games = 0

        self.stdout.write(f"Backfill from {start_date} to {today_utc} (UTC), days={days}")

        d = start_date
        while d <= today_utc:
            yyyymmdd = d.strftime("%Y%m%d")
            url = DATA_NBA_SCOREBOARD_URL.format(yyyymmdd=yyyymmdd)

            try:
                r = session.get(url, timeout=timeout)
                if r.status_code != 200:
                    skipped_days += 1
                    if not quiet:
                        self.stdout.write(self.style.WARNING(f"[SKIP] {yyyymmdd} status={r.status_code}"))
                    d += timedelta(days=1)
                    time.sleep(sleep_s)
                    continue

                payload = r.json()
                games = payload.get("games") or []
            except Exception as e:
                skipped_days += 1
                if not quiet:
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

                    # data.nba.net 的狀態
                    status = _safe_int(g.get("statusNum"), 1)  # 1 scheduled, 2 live, 3 final

                    # vTeam = away, hTeam = home
                    away = g.get("vTeam") or {}
                    home = g.get("hTeam") or {}

                    away_id = _safe_int(away.get("teamId"), 0)
                    home_id = _safe_int(home.get("teamId"), 0)
                    if home_id <= 0 or away_id <= 0:
                        skipped_games += 1
                        continue

                    away_abbr = (away.get("triCode") or "").strip()
                    home_abbr = (home.get("triCode") or "").strip()

                    # data.nba.net 這份 scoreboard 有時不給 city/name，我們就用縮寫先頂著
                    away_name = away_abbr or f"TEAM_{away_id}"
                    home_name = home_abbr or f"TEAM_{home_id}"

                    start_time = _parse_utc_iso(g.get("startTimeUTC") or "")
                    if start_time is None:
                        start_time = datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=dt_timezone.utc)

                    away_score = _safe_int(away.get("score"), 0)
                    home_score = _safe_int(home.get("score"), 0)

                    with transaction.atomic():
                        away_team, away_created = Team.objects.update_or_create(
                            nba_team_id=away_id,
                            defaults={"name": away_name, "city": "", "abbr": away_abbr},
                        )
                        home_team, home_created = Team.objects.update_or_create(
                            nba_team_id=home_id,
                            defaults={"name": home_name, "city": "", "abbr": home_abbr},
                        )

                        created_teams += int(home_created) + int(away_created)
                        updated_teams += int(not home_created) + int(not away_created)

                        winner = None
                        if status == 3:
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

            if not quiet:
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
