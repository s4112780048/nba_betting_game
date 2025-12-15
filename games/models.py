from django.db import models

class Team(models.Model):
    nba_team_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=60)
    city = models.CharField(max_length=60, blank=True)
    abbr = models.CharField(max_length=5, blank=True)

    def __str__(self):
        return self.abbr or self.name

class Game(models.Model):
    nba_game_id = models.CharField(max_length=20, unique=True)
    start_time_utc = models.DateTimeField()
    status = models.IntegerField(default=1)  # 1 scheduled, 2 live, 3 final

    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_games")
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_games")

    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)
    winner = models.ForeignKey(Team, null=True, blank=True, on_delete=models.PROTECT, related_name="wins")

    def __str__(self):
        return f"{self.away_team} @ {self.home_team}"
