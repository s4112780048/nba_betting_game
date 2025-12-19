import time
from datetime import datetime, timedelta, timezone as dt_timezone

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from games.models import Game, Team


ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


def _parse_iso_to_utc(s: str):
    """
    ESPN often returns ISO like: 2025-12-19T00:30Z or with offset
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


def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _map_status(espn_status: dict) -> int:
    """
    Return:
      1 scheduled
      2 live
      3 final
    """
    st = espn_status or {}
    typ = st.get("type") or {}
    state = (typ.get("state") or "").lower()          # pre / in / post
    completed = bool(typ.get("completed", False))

    if completed or state == "post":
        return 3
    if state == "in":
        return 2
    return 1


class Command(BaseCommand):
    help = "Sync scores/status from ESPN scoreboard for past N days (match by team abbr + time window)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=3, help="How many days back to sync (default 3).")
        parser.add_argument("--sleep", type=float, default=0.25, help="Sleep seconds between requests.")
        parser.add_argument("--timeout", type=float, default=12.0, help="HTTP timeout seconds.")
        parser.add_argument("--quiet", action="store_true", help="Less logs.")

    def handle(self, *args, **options):
        days = max(1, int(options["days"]))
        sleep_s = max(0.0, float(options["sleep"]))
        timeout = float(options["timeout"])
        quiet = bool(options["quiet"])

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (NBA Betting Django; +https://example.com)",
                "Accept": "application/json,text/plain,*/*",
            }
        )

        # use UTC date range
        today_utc = timezone.now().astimezone(dt_timezone.utc).date()
        start_date = today_utc - timedelta(days=days)

        matched = 0
        updated = 0
        skipped_days = 0
        skipped_events = 0

        self.stdout.write(f"ESPN sync from {start_date} to {today_utc} (UTC), days={days}")

        d = start_date
        while d <= today_utc:
            yyyymmdd = d.strftime("%Y%m%d")

            try:
                r = session.get(
                    ESPN_SCOREBOARD_URL,
                    params={"dates": yyyymmdd},
                    timeout=timeout,
                )
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

            # process events
            for ev in events:
                try:
                    competitions = ev.get("competitions") or []
                    if not competitions:
                        skipped_events += 1
                        continue

                    comp = competitions[0]
                    competitors = comp.get("competitors") or []
                    if len(competitors) < 2:
                        skipped_events += 1
                        continue

                    # get home/away
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

                    home_team = home.get("team") or {}
                    away_team = away.get("team") or {}

                    home_abbr = (home_team.get("abbreviation") or "").strip().upper()
                    away_abbr = (away_team.get("abbreviation") or "").strip().upper()
                    if not home_abbr or not away_abbr:
                        skipped_events += 1
                        continue

                    start_dt_utc = _parse_iso_to_utc(comp.get("date") or ev.get("date") or "")
                    if start_dt_utc is None:
                        # fallback: use that day noon UTC
                        start_dt_utc = datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=dt_timezone.utc)

                    status = _map_status(comp.get("status") or ev.get("status") or {})

                    home_score = _safe_int(home.get("score"), 0)
                    away_score = _safe_int(away.get("score"), 0)

                    # 🔥 Match to your existing Game (created by NBA CDN) using:
                    # - same team abbreviations
                    # - time window +- 12 hours around ESPN start time
                    lo = start_dt_utc - timedelta(hours=12)
                    hi = start_dt_utc + timedelta(hours=12)

                    game = (
                        Game.objects.select_related("home_team", "away_team")
                        .filter(
                            start_time_utc__gte=lo,
                            start_time_utc__lte=hi,
                            home_team__abbr__iexact=home_abbr,
                            away_team__abbr__iexact=away_abbr,
                        )
                        .order_by("start_time_utc")
                        .first()
                    )
                    if not game:
                        # some feeds swap; try reversed just in case
                        game = (
                            Game.objects.select_related("home_team", "away_team")
                            .filter(
                                start_time_utc__gte=lo,
                                start_time_utc__lte=hi,
                                home_team__abbr__iexact=away_abbr,
                                away_team__abbr__iexact=home_abbr,
                            )
                            .order_by("start_time_utc")
                            .first()
                        )
                        if game:
                            # if reversed match, swap scores too
                            home_score, away_score = away_score, home_score
                        else:
                            skipped_events += 1
                            continue

                    matched += 1

                    with transaction.atomic():
                        changed = False

                        if game.status != status:
                            game.status = status
                            changed = True

                        if game.home_score != home_score or game.away_score != away_score:
                            game.home_score = home_score
                            game.away_score = away_score
                            changed = True

                        # winner (final only)
                        if status == 3:
                            winner = None
                            if home_score > away_score:
                                winner = game.home_team
                            elif away_score > home_score:
                                winner = game.away_team
                            if game.winner_id != (winner.id if winner else None):
                                game.winner = winner
                                changed = True

                        if changed:
                            game.save(update_fields=["status", "home_score", "away_score", "winner"])
                            updated += 1

                except Exception:
                    skipped_events += 1
                    continue

            if not quiet:
                self.stdout.write(f"[OK] {yyyymmdd} events={len(events)} matched={matched} updated={updated}")

            d += timedelta(days=1)
            time.sleep(sleep_s)

        self.stdout.write(
            self.style.SUCCESS(
                f"ESPN sync done. matched={matched} updated={updated} skipped_days={skipped_days} skipped_events={skipped_events}"
            )
        )
