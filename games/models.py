# games/models.py
from django.db import models
from django.utils import timezone

class Team(models.Model):
    abbr = models.CharField(max_length=8, unique=True)  # 以縮寫當唯一鍵最穩
    name = models.CharField(max_length=80, blank=True, default="")
    city = models.CharField(max_length=80, blank=True, default="")

    def __str__(self):
        return self.abbr

class Game(models.Model):
    # 來源：只用 ESPN
    SOURCE_CHOICES = [
        ("ESPN", "ESPN"),
    ]
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="ESPN")
    source_game_id = models.CharField(max_length=40, unique=True)  # ESPN event id

    start_time_utc = models.DateTimeField(db_index=True)

    # 1 scheduled, 2 live, 3 final
    status = models.IntegerField(default=1, db_index=True)

    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_games")
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_games")

    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)
    winner = models.ForeignKey(Team, null=True, blank=True, on_delete=models.PROTECT, related_name="wins")

    # 避免重複派彩
    settled_at = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def mark_settled(self):
        self.settled_at = timezone.now()
        self.save(update_fields=["settled_at"])

    def __str__(self):
        return f"{self.away_team.abbr} @ {self.home_team.abbr}"
