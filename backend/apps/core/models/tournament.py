from datetime import time

from django.conf import settings
from django.db import models


class Tournament(models.Model):
    class TournamentType(models.TextChoices):
        POOLS = "pools", "Round-robin pools"
        BRACKET = "bracket", "Elimination bracket"
        HYBRID = "hybrid", "Pools + bracket"

    class Status(models.TextChoices):
        GENERATED = "generated", "Generated"
        CANCELLED = "cancelled", "Cancelled"

    club = models.ForeignKey(
        "core.Club",
        on_delete=models.CASCADE,
        related_name="tournaments",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_tournaments",
    )
    teams = models.ManyToManyField(
        "core.Team",
        related_name="tournaments",
        blank=True,
    )
    name = models.CharField(max_length=255)
    tournament_type = models.CharField(max_length=16, choices=TournamentType.choices)
    number_of_teams = models.PositiveIntegerField()
    pool_count = models.PositiveIntegerField(default=0)
    teams_per_pool = models.PositiveIntegerField(default=0)
    teams_qualifying_per_pool = models.PositiveIntegerField(default=0)
    match_duration_minutes = models.PositiveIntegerField(default=90)
    scoring_format = models.CharField(max_length=120, default="Best of 3 to 25")
    start_date = models.DateField()
    start_time = models.TimeField(default=time(18, 0))
    venue = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.GENERATED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.club.name})"


class TournamentPool(models.Model):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="pools",
    )
    name = models.CharField(max_length=64)
    pool_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["pool_order", "id"]

    def __str__(self) -> str:
        return f"{self.tournament.name} - {self.name}"


class TournamentFixture(models.Model):
    class StageType(models.TextChoices):
        POOL = "pool", "Pool"
        BRACKET = "bracket", "Bracket"

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="fixtures",
    )
    pool = models.ForeignKey(
        TournamentPool,
        on_delete=models.CASCADE,
        related_name="fixtures",
        null=True,
        blank=True,
    )
    training_session = models.OneToOneField(
        "core.TrainingSession",
        on_delete=models.SET_NULL,
        related_name="tournament_fixture",
        null=True,
        blank=True,
    )
    stage_type = models.CharField(max_length=16, choices=StageType.choices)
    round_number = models.PositiveIntegerField(default=1)
    round_label = models.CharField(max_length=120)
    fixture_order = models.PositiveIntegerField(default=1)
    home_team = models.ForeignKey(
        "core.Team",
        on_delete=models.SET_NULL,
        related_name="home_tournament_fixtures",
        null=True,
        blank=True,
    )
    away_team = models.ForeignKey(
        "core.Team",
        on_delete=models.SET_NULL,
        related_name="away_tournament_fixtures",
        null=True,
        blank=True,
    )
    placeholder_home_label = models.CharField(max_length=120, blank=True)
    placeholder_away_label = models.CharField(max_length=120, blank=True)
    scheduled_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["stage_type", "round_number", "fixture_order", "id"]

    def __str__(self) -> str:
        return f"{self.tournament.name} - {self.round_label}"
