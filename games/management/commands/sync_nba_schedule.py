from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from games.models import Team, Game

class Command(BaseCommand):
    help = "Sync NBA schedule (DO NOT overwrite scores)."

    def handle(self, *args, **options):
        # TODO: 這裡用你原本抓 schedule 的程式碼拿到 games_data
        # games_data = [...]
        games_data = []  # 你把這行換成你原本的資料來源

        created_teams = updated_teams = 0
        created_games = updated_games = 0
        skipped = 0

        for g in games_data:
            try:
                # TODO: 你要用你原本的欄位來源填這些值
                game_id = str(g["game_id"])
                start_time = g["start_time_utc"]  # aware datetime (UTC)
                home_id = int(g["home_team_id"])
                away_id = int(g["away_team_id"])

                home_abbr = g.get("home_abbr", "")
                away_abbr = g.get("away_abbr", "")
                home_name = g.get("home_name") or home_abbr or f"TEAM_{home_id}"
                away_name = g.get("away_name") or away_abbr or f"TEAM_{away_id}"
                home_city = g.get("home_city", "")
                away_city = g.get("away_city", "")

                with transaction.atomic():
                    home_team, hc = Team.objects.update_or_create(
                        nba_team_id=home_id,
                        defaults={"name": home_name, "city": home_city, "abbr": home_abbr},
                    )
                    away_team, ac = Team.objects.update_or_create(
                        nba_team_id=away_id,
                        defaults={"name": away_name, "city": away_city, "abbr": away_abbr},
                    )
                    created_teams += int(hc) + int(ac)
                    updated_teams += int(not hc) + int(not ac)

                    # ✅ 關鍵：用 get_or_create，已存在就不要把比分/勝負覆蓋成 0
                    obj, created = Game.objects.get_or_create(
                        nba_game_id=game_id,
                        defaults={
                            "start_time_utc": start_time,
                            "status": 1,  # scheduled
                            "home_team": home_team,
                            "away_team": away_team,
                            "home_score": 0,
                            "away_score": 0,
                            "winner": None,
                        },
                    )

                    if created:
                        created_games += 1
                    else:
                        # ✅ 已存在：只更新「賽程資訊」
                        changed = False
                        if obj.start_time_utc != start_time:
                            obj.start_time_utc = start_time
                            changed = True
                        if obj.home_team_id != home_team.id:
                            obj.home_team = home_team
                            changed = True
                        if obj.away_team_id != away_team.id:
                            obj.away_team = away_team
                            changed = True

                        if changed:
                            obj.save(update_fields=["start_time_utc", "home_team", "away_team"])
                            updated_games += 1

            except Exception as e:
                skipped += 1
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Schedule synced. teams(created={created_teams}, updated={updated_teams}) "
                f"games(created={created_games}, updated={updated_games}) skipped={skipped}"
            )
        )
