from __future__ import annotations

from django.db import models
from django.db.models import Q


class Team(models.Model):
    # legacy
    nba_team_id = models.IntegerField(null=True, blank=True, db_index=True)

    # new (ESPN)
    source = models.CharField(max_length=20, default="ESPN", db_index=True)
    source_team_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    name = models.CharField(max_length=100, blank=True, default="")
    abbreviation = models.CharField(max_length=10, blank=True, default="", db_index=True)

    logo_url = models.URLField(blank=True, default="")

    # ✅ 允許 NULL，避免對既有資料要求 default
    created_at = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True, auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_team_id"],
                condition=Q(source_team_id__isnull=False),
                name="uniq_team_source_source_team_id",
            )
        ]

    def __str__(self) -> str:
        return self.abbreviation or self.name or f"Team#{self.id}"


class Game(models.Model):
    # legacy
    nba_game_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    # new (ESPN)
    source = models.CharField(max_length=20, default="ESPN", db_index=True)
    source_game_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    game_date = models.DateField(null=True, blank=True, db_index=True)
    start_time_utc = models.DateTimeField(null=True, blank=True)

    # ESPN status.state: pre / in / post
    status = models.CharField(max_length=20, default="pre", db_index=True)

    home_team = models.ForeignKey(Team, related_name="home_games", null=True, blank=True, on_delete=models.PROTECT)
    away_team = models.ForeignKey(Team, related_name="away_games", null=True, blank=True, on_delete=models.PROTECT)

    home_abbr = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    away_abbr = models.CharField(max_length=10, null=True, blank=True, db_index=True)

    home_score = models.IntegerField(null=True, blank=True, default=0)
    away_score = models.IntegerField(null=True, blank=True, default=0)

    winner = models.ForeignKey(Team, related_name="won_games", null=True, blank=True, on_delete=models.SET_NULL)

    is_final = models.BooleanField(default=False)

    settled = models.BooleanField(default=False, db_index=True)
    settled_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # ✅ 允許 NULL，避免對既有資料要求 default
    created_at = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True, auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_game_id"],
                condition=Q(source_game_id__isnull=False),
                name="uniq_game_source_source_game_id",
            )
        ]
        indexes = [
            models.Index(fields=["game_date", "status"]),
            models.Index(fields=["game_date", "settled"]),
        ]

    def __str__(self) -> str:
        s = self.source_game_id or self.nba_game_id or str(self.id)
        return f"{self.source}:{s}"
