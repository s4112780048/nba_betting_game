# games/management/commands/sync_scores_espn.py
import time
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from games.models import Team, Game


ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# ✅ 縮寫統一（你問 Utah：ESPN 常見是 UTA；有些來源可能會變，這邊統一）
ABBR_MAP = {
    "UTH": "UTA",
    "UTAH": "UTA",
    "PHO": "PHX",
    "BRK": "BKN",
    "BKN": "BKN",
    "GS": "GSW",
    "NY": "NYK",
    "NO": "NOP",
}

def norm_abbr(x: str) -> str:
    x = (x or "").strip().upper()
    return ABBR_MAP.get(x, x)

def _parse_iso_to_utc(s: str):
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

def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default

def _map_status(espn_status: dict) -> int:
    st = espn_status or {}
    typ = st.get("type") or {}
    state = (typ.get("state") or "").lower()   # pre / in / post
    completed = bool(typ.get("completed", False))
    if completed or state == "post":
        return 3
    if state == "in":
        return 2
    return 1

class Command(BaseCommand):
    help = "Sync schedule/scores from ESPN for past N days and forward F days. Creates/updates games."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=2, help="How many days back (default 2).")
        parser.add_argument("--forward", type=int, default=7, help="How many days forward for schedule (default 7).")
        parser.add_argument("--sleep", type=float, default=0.25, help="Sleep seconds between requests.")
        parser.add_argument("--timeout", type=float, default=12.0, help="HTTP timeout seconds.")
        parser.add_argument("--quiet", action="store_true", help="Less logs.")

    def handle(self, *args, **options):
        days = max(0, int(options["days"]))
        forward = max(0, int(options["forward"]))
        sleep_s = max(0.0, float(options["sleep"]))
        timeout = float(options["timeout"])
        quiet = bool(options["quiet"])

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (NBA Betting Django; ESPN Sync)",
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://www.espn.com/",
                "Origin": "https://www.espn.com",
                "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
            }
        )

        today_utc = timezone.now().astimezone(dt_timezone.utc).date()
        start_date = today_utc - timedelta(days=days)
        end_date = today_utc + timedelta(days=forward)

        created_games = 0
        updated_games = 0
        created_teams = 0
        updated_teams = 0
        skipped_days = 0
        skipped_events = 0

        self.stdout.write(f"ESPN sync {start_date} -> {end_date} (UTC). back={days} forward={forward}")

        d = start_date
        while d <= end_date:
            yyyymmdd = d.strftime("%Y%m%d")
            try:
                r = session.get(ESPN_SCOREBOARD_URL, params={"dates": yyyymmdd}, timeout=timeout)
                if r.status_code != 200:
                    skipped_days += 1
                    if not quiet:
                        self.stdout.write(self.style.WARNING(f"[SKIP] {yyyymmdd} status={r.status_code}"))
                    d += timedelta(days=1)
                    time.sleep(sleep_s)
                    continue

                payload = r.json()
                events = payload.get("events") or []
            except Exception as e:
                skipped_days += 1
                if not quiet:
                    self.stdout.write(self.style.WARNING(f"[SKIP] {yyyymmdd} error={e}"))
                d += timedelta(days=1)
                time.sleep(sleep_s)
                continue

            for ev in events:
                try:
                    event_id = str(ev.get("id") or "").strip()
                    if not event_id:
                        skipped_events += 1
                        continue

                    competitions = ev.get("competitions") or []
                    if not competitions:
                        skipped_events += 1
                        continue
                    comp = competitions[0]

                    competitors = comp.get("competitors") or []
                    if len(competitors) < 2:
                        skipped_events += 1
                        continue

                    home = None
                    away = None
                    for c in competitors:
                        ha = (c.get("homeAway") or "").lower()
                        if ha == "home":
                            home = c
                        elif ha == "away":
                            away = c
                    if not home or not away:
                        skipped_events += 1
                        continue

                    ht = home.get("team") or {}
                    at = away.get("team") or {}

                    home_abbr = norm_abbr(ht.get("abbreviation") or "")
                    away_abbr = norm_abbr(at.get("abbreviation") or "")
                    if not home_abbr or not away_abbr:
                        skipped_events += 1
                        continue

                    start_dt_utc = _parse_iso_to_utc(comp.get("date") or ev.get("date") or "")
                    if start_dt_utc is None:
                        start_dt_utc = datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=dt_timezone.utc)

                    status = _map_status(comp.get("status") or ev.get("status") or {})
                    home_score = _safe_int(home.get("score"), 0)
                    away_score = _safe_int(away.get("score"), 0)

                    home_name = (ht.get("displayName") or "").strip()
                    away_name = (at.get("displayName") or "").strip()

                    with transaction.atomic():
                        home_team, home_created = Team.objects.update_or_create(
                            abbr=home_abbr,
                            defaults={"name": home_name, "city": ""},
                        )
                        away_team, away_created = Team.objects.update_or_create(
                            abbr=away_abbr,
                            defaults={"name": away_name, "city": ""},
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
                            source="ESPN",
                            source_game_id=event_id,
                            defaults={
                                "start_time_utc": start_dt_utc,
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
                    skipped_events += 1
                    continue

            if not quiet:
                self.stdout.write(f"[OK] {yyyymmdd} events={len(events)}")

            d += timedelta(days=1)
            time.sleep(sleep_s)

        self.stdout.write(
            self.style.SUCCESS(
                f"ESPN sync done. teams(created={created_teams}, updated={updated_teams}) "
                f"games(created={created_games}, updated={updated_games}) "
                f"skipped_days={skipped_days} skipped_events={skipped_events}"
            )
        )
