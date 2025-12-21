from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import requests


@dataclass
class EspnTeam:
    abbreviation: str
    display_name: str
    score: int


@dataclass
class EspnGame:
    source: str
    source_game_id: str
    status: str  # "pre" | "in" | "post"
    home: EspnTeam
    away: EspnTeam


class EspnClient:
    """
    ESPN 非公開 scoreboard API
    會嘗試多個 endpoint（避免某條 404 就全掛）
    """

    URL_CANDIDATES = [
        # ✅ 最常用、穩定
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        # ✅ 另一條也常見
        "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        # ⚠️ 舊版（你現在用的這條有時會 404，保留當最後 fallback）
        "https://site.web.api.espn.com/apis/v2/sports/basketball/nba/scoreboard",
    ]

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; nba-betting-game/1.0)",
                "Accept": "application/json,text/plain,*/*",
            }
        )

    def fetch_scoreboard(self, day: date) -> List[EspnGame]:
        ymd = day.strftime("%Y%m%d")
        last_err: Optional[Exception] = None

        for url in self.URL_CANDIDATES:
            try:
                r = self.session.get(url, params={"dates": ymd}, timeout=self.timeout)
                if r.status_code == 404:
                    # 這條 endpoint 不存在就換下一條
                    continue
                r.raise_for_status()
                data = r.json()
                return self._parse_scoreboard(data)
            except Exception as e:
                last_err = e
                continue

        # 全部都失敗才拋錯，讓你看得到真正原因
        if last_err:
            raise last_err
        return []

    def _parse_scoreboard(self, data: dict) -> List[EspnGame]:
        events = data.get("events") or []
        out: List[EspnGame] = []

        for ev in events:
            event_id = str(ev.get("id", "")).strip()
            comps = ev.get("competitions") or []
            if not event_id or not comps:
                continue

            comp0 = comps[0]
            status_state = (
                (comp0.get("status") or {})
                .get("type", {})
                .get("state", "")
            )
            status_state = (status_state or "").strip().lower()

            competitors = comp0.get("competitors") or []
            home = self._pick_team(competitors, "home")
            away = self._pick_team(competitors, "away")
            if not home or not away:
                continue

            out.append(
                EspnGame(
                    source="ESPN",
                    source_game_id=event_id,
                    status=status_state or "pre",
                    home=home,
                    away=away,
                )
            )

        return out

    def _pick_team(self, competitors: list, home_away: str) -> Optional[EspnTeam]:
        for c in competitors:
            if (c.get("homeAway") or "").lower() != home_away:
                continue
            team = c.get("team") or {}
            abbr = (team.get("abbreviation") or "").strip()
            name = (team.get("displayName") or team.get("shortDisplayName") or "").strip()
            score_raw = c.get("score")
            try:
                score = int(score_raw) if score_raw not in (None, "") else 0
            except Exception:
                score = 0
            if not abbr and not name:
                return None
            return EspnTeam(abbreviation=abbr or "", display_name=name or abbr or "", score=score)
        return None
