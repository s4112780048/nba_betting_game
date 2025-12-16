from pathlib import Path
import requests

from django.conf import settings
from django.core.management.base import BaseCommand
from games.models import Team


def is_official_nba_team_id(team_id: int) -> bool:
    # NBA 正規隊伍 teamId 通常是 16106127xx
    return str(team_id).startswith("161061")


class Command(BaseCommand):
    help = "Download NBA (official teams only) logos into static/team_logos (svg)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Re-download even if file exists.")
        parser.add_argument("--include-non-nba", action="store_true", help="Also try non-NBA team IDs (may 403/404).")

    def handle(self, *args, **options):
        out_dir = Path(settings.BASE_DIR) / "static" / "team_logos"
        out_dir.mkdir(parents=True, exist_ok=True)

        force = options["force"]
        include_non_nba = options["include_non_nba"]

        ok, skip_exist, skip_non_nba, fail = 0, 0, 0, 0

        for t in Team.objects.order_by("nba_team_id"):
            team_id = t.nba_team_id

            if (not include_non_nba) and (not is_official_nba_team_id(team_id)):
                skip_non_nba += 1
                continue

            fp = out_dir / f"{team_id}.svg"
            if fp.exists() and not force:
                skip_exist += 1
                continue

            url = f"https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"

            try:
                r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200 or not r.content:
                    fail += 1
                    self.stderr.write(f"[FAIL] {t} id={team_id} status={r.status_code}")
                    continue

                fp.write_bytes(r.content)
                ok += 1
                self.stdout.write(f"[OK] {t} -> {fp.name}")

            except Exception as e:
                fail += 1
                self.stderr.write(f"[ERR] {t} id={team_id} {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Done. downloaded={ok}, skipped_exist={skip_exist}, skipped_non_nba={skip_non_nba}, failed={fail}, dir={out_dir}"
        ))
