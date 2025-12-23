# games/models.py
from django.db import models
from django.utils import timezone


class Team(models.Model):
    SOURCE_CHOICES = (
        ("espn", "ESPN"),
    )

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="espn")
    source_team_id = models.CharField(max_length=64, db_index=True)  # ESPN team id
    name = models.CharField(max_length=120)
    abbr = models.CharField(max_length=10, blank=True, default="")
    logo_url = models.URLField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "source_team_id"], name="uniq_team_source_id")
        ]

    def __str__(self):
        return f"{self.abbr or self.name} ({self.source}:{self.source_team_id})"


class Game(models.Model):
    SOURCE_CHOICES = (
        ("espn", "ESPN"),
    )
    STATUS_CHOICES = (
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("final", "Final"),
        ("postponed", "Postponed"),
        ("canceled", "Canceled"),
        ("unknown", "Unknown"),
    )
    SETTLEMENT_CHOICES = (
        ("pending", "Pending"),
        ("settled", "Settled"),
        ("voided", "Voided"),
    )

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="espn")
    source_game_id = models.CharField(max_length=64, db_index=True)  # ESPN event id

    start_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unknown")

    home_team = models.ForeignKey(Team, related_name="home_games", on_delete=models.PROTECT)
    away_team = models.ForeignKey(Team, related_name="away_games", on_delete=models.PROTECT)

    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)

    # winner: "home" / "away" / "draw" / ""
    winner = None  # property below

    settlement_status = models.CharField(max_length=20, choices=SETTLEMENT_CHOICES, default="pending")
    settled_at = models.DateTimeField(null=True, blank=True)

    raw_json = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "source_game_id"], name="uniq_game_source_id")
        ]
        ordering = ("-start_time", "-id")

    @property
    def winner(self) -> str:
        if self.status != "final":
            return ""
        if self.home_score is None or self.away_score is None:
            return ""
        if self.home_score > self.away_score:
            return "home"
        if self.away_score > self.home_score:
            return "away"
        return "draw"

    def is_final(self) -> bool:
        return self.status == "final"

    def mark_settled(self):
        self.settlement_status = "settled"
        self.settled_at = timezone.now()
