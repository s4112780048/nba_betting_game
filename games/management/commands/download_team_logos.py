from __future__ import annotations

from pathlib import Path
import requests

from django.conf import settings
from django.core.management.base import BaseCommand

from games.models import Team

# 以「你資料庫 Team.abbr」為準，下載 NBA 官方 svg
# 檔名：static/team_logos/{ABBR}.svg
NBA_TEAM_ID_BY_ABBR = {
    "ATL": 1610612737,
    "BOS": 1610612738,
    "BKN": 1610612751,
    "CHA": 1610612766,
    "CHI": 1610612741,
    "CLE": 1610612739,
    "DAL": 1610612742,
    "DEN": 1610612743,
    "DET": 1610612765,
    "GSW": 1610612744,
    "HOU": 1610612745,
    "IND": 1610612754,
    "LAC": 1610612746,
    "LAL": 1610612747,
    "MEM": 1610612763,
    "MIA": 1610612748,
    "MIL": 1610612749,
    "MIN": 1610612750,
    "NOP": 1610612740,
    "NYK": 1610612752,
    "OKC": 1610612760,
    "ORL": 1610612753,
    "PHI": 1610612755,
    "PHX": 1610612756,
    "POR": 1610612757,
    "SAC": 1610612758,

    # ✅ 你畫面上用的是 SA / WSH，所以直接用這兩個 abbr 存檔
    "SA": 1610612759,
    "WSH": 1610612764,

    "TOR": 1610612761,
    "UTA": 1610612762,
}

def norm_abbr(abbr: str) -> str:
    return (abbr or "").strip().upper()

class Command(BaseCommand):
    help = "Download NBA team logos into static/team_logos (svg). Filename is ABBR.svg"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Re-download even if file exists.")

    def handle(self, *args, **options):
        out_dir = Path(settings.BASE_DIR) / "static" / "team_logos"
        out_dir.mkdir(parents=True, exist_ok=True)

        force = bool(options["force"])
        ok, skip_exist, skip_unknown, fail = 0, 0, 0, 0

        qs = Team.objects.all().order_by("abbr", "id")

        for t in qs:
            abbr = norm_abbr(getattr(t, "abbr", ""))
            if not abbr:
                skip_unknown += 1
                continue

            team_id = NBA_TEAM_ID_BY_ABBR.get(abbr)
            if not team_id:
                skip_unknown += 1
                self.stdout.write(f"[SKIP] unknown abbr={abbr} (no NBA teamId mapping): {t}")
                continue

            fp = out_dir / f"{abbr}.svg"
            if fp.exists() and not force:
                skip_exist += 1
                continue

            url = f"https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"

            try:
                r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200 or not r.content:
                    fail += 1
                    self.stderr.write(f"[FAIL] {abbr} id={team_id} status={r.status_code}")
                    continue

                fp.write_bytes(r.content)
                ok += 1
                self.stdout.write(f"[OK] {abbr} -> {fp.name} ({url})")
            except Exception as e:
                fail += 1
                self.stderr.write(f"[ERR] {abbr} id={team_id} {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Done. downloaded={ok}, skipped_exist={skip_exist}, skipped_unknown={skip_unknown}, failed={fail}, dir={out_dir}"
        ))
