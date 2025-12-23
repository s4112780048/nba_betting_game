# games/espn.py
import requests
from datetime import date
from django.utils import timezone
from .models import Team, Game

# ESPN NBA scoreboard (公開可讀；不需要 API key)
SCOREBOARD_URL = "https://site.web.api.espn.com/apis/v2/sports/basketball/nba/scoreboard"


def fetch_scoreboard(target_date: date | None = None) -> dict:
    params = {}
    if target_date:
        params["dates"] = target_date.strftime("%Y%m%d")
    r = requests.get(SCOREBOARD_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def upsert_from_scoreboard(payload: dict) -> tuple[int, int]:
    """
    Returns: (games_upserted, teams_upserted)
    """
    teams_upserted = 0
    games_upserted = 0

    events = payload.get("events", []) or []
    for ev in events:
        event_id = str(ev.get("id", ""))  # source_game_id
        if not event_id:
            continue

        competitions = ev.get("competitions", []) or []
        if not competitions:
            continue

        comp = competitions[0]
        competitors = comp.get("competitors", []) or []
        if len(competitors) != 2:
            continue

        # ESPN competitor: home/away
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue

        def upsert_team(team_obj: dict):
            nonlocal teams_upserted
            t = team_obj.get("team", {}) or {}
            tid = str(t.get("id", ""))
            if not tid:
                return None
            name = t.get("displayName") or t.get("name") or f"Team {tid}"
            abbr = t.get("abbreviation") or ""
            logo = ""
            logos = t.get("logos", []) or []
            if logos:
                logo = logos[0].get("href") or ""

            team, created = Team.objects.update_or_create(
                source="espn",
                source_team_id=tid,
                defaults={"name": name, "abbr": abbr, "logo_url": logo},
            )
            if created:
                teams_upserted += 1
            return team

        home_team = upsert_team(home)
        away_team = upsert_team(away)
        if not home_team or not away_team:
            continue

        # time/status
        dt_str = comp.get("date")  # ISO string
        start_time = None
        if dt_str:
            try:
                start_time = timezone.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except Exception:
                start_time = None

        status_obj = comp.get("status", {}) or {}
        state = (status_obj.get("type", {}) or {}).get("state") or "unknown"
        # ESPN state: pre / in / post
        if state == "pre":
            status = "scheduled"
        elif state == "in":
            status = "in_progress"
        elif state == "post":
            status = "final"
        else:
            status = "unknown"

        def parse_score(c):
            s = c.get("score")
            try:
                return int(s)
            except Exception:
                return None

        home_score = parse_score(home)
        away_score = parse_score(away)

        _, created = Game.objects.update_or_create(
            source="espn",
            source_game_id=event_id,
            defaults={
                "start_time": start_time,
                "status": status,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "raw_json": ev,
            },
        )
        games_upserted += 1

    return games_upserted, teams_upserted
