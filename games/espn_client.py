# games/espn_client.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

import requests
from django.utils.dateparse import parse_datetime


ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


@dataclass(frozen=True)
class TeamPayload:
    source_team_id: str
    name: str
    abbr: str
    logo_url: str


@dataclass(frozen=True)
class GamePayload:
    source_game_id: str
    start_time: Optional[str]  # iso string
    status: str  # scheduled / in_progress / final / postponed / canceled / unknown
    home: TeamPayload
    away: TeamPayload
    home_score: Optional[int]
    away_score: Optional[int]
    raw: Dict[str, Any]


class EspnClient:
    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def fetch_scoreboard(self, day: date) -> List[GamePayload]:
        ymd = day.strftime("%Y%m%d")
        r = requests.get(
            ESPN_SCOREBOARD_URL,
            params={"dates": ymd, "limit": 1000},
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()
        data = r.json()

        events = data.get("events", []) or []
        out: List[GamePayload] = []

        for e in events:
            comp = (e.get("competitions") or [{}])[0]
            competitors = comp.get("competitors") or []
            home_c = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away_c = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home_c or not away_c:
                continue

            status = self._map_status(e)

            home_team = self._parse_team(home_c)
            away_team = self._parse_team(away_c)

            home_score = self._to_int(home_c.get("score"))
            away_score = self._to_int(away_c.get("score"))

            out.append(
                GamePayload(
                    source_game_id=str(e.get("id", "")),
                    start_time=e.get("date"),
                    status=status,
                    home=home_team,
                    away=away_team,
                    home_score=home_score,
                    away_score=away_score,
                    raw=e,
                )
            )
        return out

    def _parse_team(self, competitor: Dict[str, Any]) -> TeamPayload:
        t = competitor.get("team") or {}
        return TeamPayload(
            source_team_id=str(t.get("id", "")),
            name=str(t.get("displayName", "")),
            abbr=str(t.get("abbreviation", "")) or "",
            logo_url=str(t.get("logo", "")) or "",
        )

    def _map_status(self, event: Dict[str, Any]) -> str:
        st = (event.get("status") or {}).get("type") or {}
        state = (st.get("state") or "").lower()     # pre / in / post
        name = (st.get("name") or "").upper()       # STATUS_FINAL / STATUS_SCHEDULED / ...
        desc = (st.get("description") or "").lower()

        if "POSTPON" in name or "postpon" in desc:
            return "postponed"
        if "CANCEL" in name or "cancell" in desc:
            return "canceled"

        if state == "pre":
            return "scheduled"
        if state == "in":
            return "in_progress"
        if state == "post":
            return "final"

        # fallback
        if "FINAL" in name:
            return "final"
        if "SCHED" in name:
            return "scheduled"

        return "unknown"

    def _to_int(self, v: Any) -> Optional[int]:
        try:
            return int(v)
        except Exception:
            return None
