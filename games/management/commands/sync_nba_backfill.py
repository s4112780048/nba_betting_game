import time
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from games.models import Team, Game

NBA_SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/scoreboard_{yyyymmdd}.json"
NBA_BOXSCORE_URL = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"


def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _parse_utc_iso(s: str):
    # NBA CDN often returns ISO like '2025-12-15T00:00:00Z'
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


def _winner_team(status: int, home_team: Team, away_team: Team, home_score: int, away_score: int):
    if status != 3:
        return None
    if home_score > away_score:
        return home_team
    if away_score > home_score:
        return away_team
    return None


def _fetch_json_with_retry(session: requests.Session, url: str, timeout: float, retries: int = 3):
    last_err = None
    for i in range(retries):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.json(), 200
            last_err = f"status={r.status_code}"
            # 403/429 通常是限流，稍等再試
            if r.status_code in (403, 429):
                time.sleep(0.6 * (i + 1))
                continue
            return None, r.status_code
        except Exception as e:
            last_err = str(e)
            time.sleep(0.6 * (i + 1))
    return None, last_err


def _extract_from_boxscore(payload: dict):
    """
    boxscore_{gameId}.json 典型結構：
    {
      "game": {
        "gameId": "...",
        "gameStatus": 3,
        "gameTimeUTC": "...Z",
        "homeTeam": {..., "score": 112},
        "awayTeam": {..., "score": 105}
      }
    }
    """
    game = (payload or {}).get("game") or {}
    status = _safe_int(game.get("gameStatus"), 1)
    start_time = _parse_utc_iso(game.get("gameTimeUTC") or "")

    home = game.get("homeTeam") or {}
    away = game.get("awayTeam") or {}

    home_id = _safe_int(home.get("teamId"), 0)
    away_id = _safe_int(away.get("teamId"), 0)

    home_score = _safe_int(home.get("score"), 0)
    away_score = _safe_int(away.get("score"), 0)

    home_abbr = (home.get("teamTricode") or "").strip()
    away_abbr = (away.get("teamTricode") or "").strip()

    home_name = (home.get("teamName") or home_abbr or f"TEAM_{home_id}").strip()
    away_name = (away.get("teamName") or away_abbr or f"TEAM_{away_id}").strip()

    home_city = (home.get("teamCity") or "").strip()
    away_city = (away.get("teamCity") or "").strip()

    return {
        "status": status,
        "start_time": start_time,
        "home": {"id": home_id, "abbr": home_abbr, "name": home_name, "city": home_city, "score": home_score},
        "away": {"id": away_id, "abbr": away_abbr, "name": away_name, "city": away_city, "score": away_score},
    }


class Command(BaseCommand):
    help = "Backfill NBA games/scores/status for past N days using NBA CDN scoreboard + boxscore fallback."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14, help="How many days back to sync (default 14).")
        parser.add_argument("--sleep", type=float, default=0.20, help="Sleep seconds between requests.")
        parser.add_argument("--timeout", type=float, default=12.0, help="HTTP timeout seconds.")
        parser.add_argument("--quiet", action="store_true", help="Less per-day logs.")
        parser.add_argument("--boxsleep", type=float, default=0.10, help="Extra sleep before boxscore fetch.")

    def handle(self, *args, **options):
        days = max(1, int(options["days"]))
        sleep_s = max(0.0, float(options["sleep"]))
        boxsleep = max(0.0, float(options["boxsleep"]))
        timeout = float(options["timeout"])
        quiet = bool(options["quiet"])

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; NBA Betting Django)",
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://www.nba.com/",
                "Origin": "https://www.nba.com",
            }
        )

        today_utc = timezone.now().astimezone(dt_timezone.utc).date()
        start_date = today_utc - timedelta(days=days)

        created_games = 0
        updated_games = 0
        created_teams = 0
        updated_teams = 0
        skipped_days = 0
        skipped_games = 0
        fixed_by_boxscore = 0
        http_403 = 0

        self.stdout.write(f"Backfill from {start_date} to {today_utc} (UTC), days={days}")

        d = start_date
        while d <= today_utc:
            yyyymmdd = d.strftime("%Y%m%d")
            url = NBA_SCOREBOARD_URL.format(yyyymmdd=yyyymmdd)

            payload, status_code = _fetch_json_with_retry(session, url, timeout=timeout, retries=3)
            if status_code == 403:
                http_403 += 1
            if not payload:
                skipped_days += 1
                if not quiet:
                    self.stdout.write(self.style.WARNING(f"[SKIP] {yyyymmdd} {status_code}"))
                d += timedelta(days=1)
                time.sleep(sleep_s)
                continue

            games = (payload.get("scoreboard") or {}).get("games") or []

            for g in games:
                try:
                    game_id = str(g.get("gameId") or "").strip()
                    if not game_id:
                        skipped_games += 1
                        continue

                    status = _safe_int(g.get("gameStatus"), 1)

                    home = g.get("homeTeam") or {}
                    away = g.get("awayTeam") or {}

                    home_id = _safe_int(home.get("teamId"), 0)
                    away_id = _safe_int(away.get("teamId"), 0)
                    if home_id <= 0 or away_id <= 0:
                        skipped_games += 1
                        continue

                    home_abbr = (home.get("teamTricode") or "").strip()
                    away_abbr = (away.get("teamTricode") or "").strip()

                    home_name = (home.get("teamName") or home_abbr or f"TEAM_{home_id}").strip()
                    away_name = (away.get("teamName") or away_abbr or f"TEAM_{away_id}").strip()

                    home_city = (home.get("teamCity") or "").strip()
                    away_city = (away.get("teamCity") or "").strip()

                    start_time = _parse_utc_iso(g.get("gameTimeUTC") or "")
                    if start_time is None:
                        start_time = datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=dt_timezone.utc)

                    home_score = _safe_int(home.get("score"), 0)
                    away_score = _safe_int(away.get("score"), 0)

                    # ✅ fallback：如果 status=2/3 但比分 0:0，用 boxscore 補齊
                    if status in (2, 3) and home_score == 0 and away_score == 0:
                        time.sleep(boxsleep)
                        box_url = NBA_BOXSCORE_URL.format(game_id=game_id)
                        box_payload, box_status = _fetch_json_with_retry(session, box_url, timeout=timeout, retries=3)
                        if box_payload:
                            info = _extract_from_boxscore(box_payload)
                            if info["home"]["id"] > 0 and info["away"]["id"] > 0:
                                status = info["status"] or status
                                if info["start_time"] is not None:
                                    start_time = info["start_time"]
                                # 只要 boxscore 有提供非 0，就覆蓋
                                if info["home"]["score"] != 0 or info["away"]["score"] != 0:
                                    home_score = info["home"]["score"]
                                    away_score = info["away"]["score"]
                                    fixed_by_boxscore += 1

                    with transaction.atomic():
                        home_team, home_created = Team.objects.update_or_create(
                            nba_team_id=home_id,
                            defaults={"name": home_name, "city": home_city, "abbr": home_abbr},
                        )
                        away_team, away_created = Team.objects.update_or_create(
                            nba_team_id=away_id,
                            defaults={"name": away_name, "city": away_city, "abbr": away_abbr},
                        )
                        created_teams += int(home_created) + int(away_created)
                        updated_teams += int(not home_created) + int(not away_created)

                        winner = _winner_team(status, home_team, away_team, home_score, away_score)

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

        if http_403 > 0:
            self.stdout.write(self.style.WARNING(f"NOTE: got HTTP 403 {http_403} times (NBA CDN may rate-limit)."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill done. teams(created={created_teams}, updated={updated_teams}) "
                f"games(created={created_games}, updated={updated_games}) "
                f"fixed_by_boxscore={fixed_by_boxscore} "
                f"skipped_days={skipped_days} skipped_games={skipped_games}"
            )
        )
session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
)

# ✅ 先暖機：進 nba.com 拿到必要 cookie，再打 CDN
try:
    session.get("https://www.nba.com/", timeout=timeout)
    time.sleep(0.8)
except Exception:
    pass
