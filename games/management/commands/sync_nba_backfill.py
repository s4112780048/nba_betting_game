import time
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from games.models import Team, Game


# 1) 新版 NBA CDN（你原本用的）
NBA_SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/scoreboard_{yyyymmdd}.json"
# 2) 舊版 data.nba.net（有時 cdn 403 就用這個救）
NBA_SCOREBOARD_URL_FALLBACK = "https://data.nba.net/10s/prod/v1/{yyyymmdd}/scoreboard.json"


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
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        return dt.astimezone(dt_timezone.utc)
    except Exception:
        return None


def _parse_fallback_date_time(g: dict, d_utc_date):
    """
    data.nba.net fallback 的時間欄位結構可能不同：
    常見：g["startTimeUTC"] / g["startTimeUTC"] or g["startTimeUTC"]...
    如果拿不到就用當天中午 UTC 當 fallback。
    """
    # 常見 key 嘗試
    for key in ("gameTimeUTC", "startTimeUTC", "startTimeUtc", "startTimeUTC", "startTimeUTC"):
        s = (g.get(key) or "").strip()
        dt = _parse_utc_iso(s)
        if dt is not None:
            return dt
    # fallback：當天 12:00 UTC
    return datetime(d_utc_date.year, d_utc_date.month, d_utc_date.day, 12, 0, 0, tzinfo=dt_timezone.utc)


def _extract_games_from_payload(payload: dict):
    """
    把不同來源的 payload 轉成 games list
    - cdn.nba.com: payload["scoreboard"]["games"]
    - data.nba.net: payload["games"]
    """
    if not isinstance(payload, dict):
        return []
    if "scoreboard" in payload:
        return (payload.get("scoreboard") or {}).get("games") or []
    if "games" in payload:
        return payload.get("games") or []
    return []


def _extract_team_dicts(g: dict):
    """
    回傳 (home_dict, away_dict) 兩個 dict
    - cdn.nba.com: g["homeTeam"], g["awayTeam"]
    - data.nba.net: g["hTeam"], g["vTeam"] 或 g["homeTeam"], g["awayTeam"]
    """
    home = g.get("homeTeam") or g.get("hTeam") or {}
    away = g.get("awayTeam") or g.get("vTeam") or {}
    return home, away


def _extract_ids_abbr_name_city(team_dict: dict, fallback_id_key="teamId"):
    """
    盡量兼容不同欄位：
    - cdn: teamId/teamTricode/teamName/teamCity/score
    - data.nba.net: teamId/triCode/nickName/city/score
    """
    team_id = _safe_int(team_dict.get("teamId") or team_dict.get("teamID") or 0, 0)

    abbr = (team_dict.get("teamTricode") or team_dict.get("triCode") or team_dict.get("tricode") or "").strip()

    name = (team_dict.get("teamName") or team_dict.get("nickName") or team_dict.get("name") or abbr or f"TEAM_{team_id}").strip()
    city = (team_dict.get("teamCity") or team_dict.get("city") or "").strip()

    score = _safe_int(team_dict.get("score") or 0, 0)

    return team_id, abbr, name, city, score


def _extract_game_id_status(g: dict):
    """
    - cdn: gameId, gameStatus (1 scheduled, 2 live, 3 final)
    - data.nba.net: gameId, statusNum (1 scheduled, 2 live, 3 final)
    """
    game_id = str(g.get("gameId") or g.get("gameID") or "").strip()
    status = _safe_int(g.get("gameStatus") or g.get("statusNum") or 1, 1)
    return game_id, status


class Command(BaseCommand):
    help = "Backfill NBA games/scores/status for past N days (cdn.nba.com, fallback data.nba.net)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14, help="How many days back to sync (default 14).")
        parser.add_argument("--sleep", type=float, default=0.20, help="Sleep seconds between requests.")
        parser.add_argument("--timeout", type=float, default=12.0, help="HTTP timeout seconds.")
        parser.add_argument("--quiet", action="store_true", help="Less per-day logs.")
        parser.add_argument("--insecure", action="store_true", help="Disable SSL verification (workaround for hostname mismatch).")

    def handle(self, *args, **options):
        days = max(1, int(options["days"]))
        sleep_s = max(0.0, float(options["sleep"]))
        timeout = float(options["timeout"])
        quiet = bool(options["quiet"])
        insecure = bool(options["insecure"])

        if insecure:
            urllib3.disable_warnings(InsecureRequestWarning)

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; NBA Betting Django)",
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://www.nba.com/",
                "Origin": "https://www.nba.com",
            }
        )

        # Django timezone.now() is aware; normalize to UTC date
        today_utc = timezone.now().astimezone(dt_timezone.utc).date()
        start_date = today_utc - timedelta(days=days)

        created_games = 0
        updated_games = 0
        created_teams = 0
        updated_teams = 0
        skipped_days = 0
        skipped_games = 0

        cdn_403_days = 0
        fallback_used_days = 0

        self.stdout.write(f"Backfill from {start_date} to {today_utc} (UTC), days={days}")

        d = start_date
        while d <= today_utc:
            yyyymmdd = d.strftime("%Y%m%d")

            # 先用 cdn
            url_primary = NBA_SCOREBOARD_URL.format(yyyymmdd=yyyymmdd)
            url_fallback = NBA_SCOREBOARD_URL_FALLBACK.format(yyyymmdd=yyyymmdd)

            payload = None
            used_fallback = False

            # ---- 1) primary: cdn.nba.com ----
            try:
                r = session.get(url_primary, timeout=timeout, verify=not insecure)
                if r.status_code == 200:
                    payload = r.json()
                else:
                    if r.status_code == 403:
                        cdn_403_days += 1
            except Exception:
                # 讓 fallback 接手
                pass

            # ---- 2) fallback: data.nba.net ----
            if payload is None:
                try:
                    r2 = session.get(url_fallback, timeout=timeout, verify=not insecure)
                    if r2.status_code == 200:
                        payload = r2.json()
                        used_fallback = True
                        fallback_used_days += 1
                except Exception as e:
                    payload = None

            if payload is None:
                skipped_days += 1
                if not quiet:
                    self.stdout.write(self.style.WARNING(f"[SKIP] {yyyymmdd} primary/fallback failed"))
                d += timedelta(days=1)
                time.sleep(sleep_s)
                continue

            games = _extract_games_from_payload(payload)

            for g in games:
                try:
                    game_id, status = _extract_game_id_status(g)
                    if not game_id:
                        skipped_games += 1
                        continue

                    home_dict, away_dict = _extract_team_dicts(g)

                    home_id, home_abbr, home_name, home_city, home_score = _extract_ids_abbr_name_city(home_dict)
                    away_id, away_abbr, away_name, away_city, away_score = _extract_ids_abbr_name_city(away_dict)

                    if home_id <= 0 or away_id <= 0:
                        skipped_games += 1
                        continue

                    # 開賽時間：cdn 用 gameTimeUTC；fallback 用 startTimeUTC/其他欄位
                    start_time = _parse_utc_iso(g.get("gameTimeUTC") or "")
                    if start_time is None:
                        start_time = _parse_fallback_date_time(g, d)

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

            if not quiet:
                tag = "FALLBACK" if used_fallback else "CDN"
                self.stdout.write(f"[OK] {yyyymmdd} games={len(games)} src={tag}")

            d += timedelta(days=1)
            time.sleep(sleep_s)

        if cdn_403_days > 0:
            self.stdout.write(self.style.WARNING(f"NOTE: cdn.nba.com returned 403 on {cdn_403_days} days."))
        if fallback_used_days > 0:
            self.stdout.write(self.style.WARNING(f"NOTE: used data.nba.net fallback on {fallback_used_days} days."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill done. teams(created={created_teams}, updated={updated_teams}) "
                f"games(created={created_games}, updated={updated_games}) "
                f"skipped_days={skipped_days} skipped_games={skipped_games}"
            )
        )
