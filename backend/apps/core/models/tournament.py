from datetime import time

from django.conf import settings
from django.db import models


class Tournament(models.Model):
    class TournamentType(models.TextChoices):
        POOLS = "pools", "Round-robin pools"
        BRACKET = "bracket", "Elimination bracket"
        HYBRID = "hybrid", "Pools + bracket"
        POOL_ONLY = "pool_only", "Pool Play"
        BRACKET_ONLY = "bracket_only", "Bracket"
        POOL_AND_BRACKET = "pool_and_bracket", "Pool + Bracket"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POOL_STAGE = "pool_stage", "Pool Stage"
        BRACKET_STAGE = "bracket_stage", "Bracket Stage"
        COMPLETED = "completed", "Completed"
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
    court_count = models.PositiveIntegerField(
        default=1,
        help_text="Parallel courts for scheduling (not the same as pool count).",
    )
    scoring_format = models.CharField(max_length=120, default="Best of 3 to 25")
    start_date = models.DateField()
    start_time = models.TimeField(default=time(9, 0))
    venue = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.club.name})"


class TournamentTeam(models.Model):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="tournament_teams",
    )
    team = models.ForeignKey(
        "core.Team",
        on_delete=models.CASCADE,
        related_name="team_tournaments",
    )
    seed = models.PositiveIntegerField(default=1)
    pool = models.ForeignKey(
        "core.Pool",
        on_delete=models.SET_NULL,
        related_name="tournament_teams",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["seed", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tournament", "team"], name="uniq_tournament_team"),
            models.UniqueConstraint(fields=["tournament", "seed"], name="uniq_tournament_seed"),
        ]

    def __str__(self) -> str:
        return f"{self.tournament.name} - {self.team.name}"


class Pool(models.Model):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="pool_groups",
    )
    name = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["tournament", "name"], name="uniq_tournament_pool_name"),
        ]

    def __str__(self) -> str:
        return f"{self.tournament.name} - {self.name}"


class TournamentMatch(models.Model):
    class MatchStatus(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ONGOING = "ongoing", "Ongoing"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="tournament_matches",
    )
    pool = models.ForeignKey(
        Pool,
        on_delete=models.CASCADE,
        related_name="matches",
        null=True,
        blank=True,
    )
    bracket_round = models.CharField(max_length=64, blank=True)
    match_number = models.PositiveIntegerField(default=1)
    team_a = models.ForeignKey(
        "core.Team",
        on_delete=models.SET_NULL,
        related_name="tournament_matches_as_team_a",
        null=True,
        blank=True,
    )
    team_b = models.ForeignKey(
        "core.Team",
        on_delete=models.SET_NULL,
        related_name="tournament_matches_as_team_b",
        null=True,
        blank=True,
    )
    team_a_score = models.PositiveIntegerField(null=True, blank=True)
    team_b_score = models.PositiveIntegerField(null=True, blank=True)
    winner_team = models.ForeignKey(
        "core.Team",
        on_delete=models.SET_NULL,
        related_name="tournament_matches_won",
        null=True,
        blank=True,
    )
    loser_team = models.ForeignKey(
        "core.Team",
        on_delete=models.SET_NULL,
        related_name="tournament_matches_lost",
        null=True,
        blank=True,
    )
    scheduled_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Override tournament match length for this game (start + duration = end).",
    )
    pool_round_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Round index within pool play (1-based), for display only.",
    )
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=MatchStatus.choices, default=MatchStatus.SCHEDULED)
    next_match = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="feeders",
        null=True,
        blank=True,
    )
    next_match_slot = models.CharField(max_length=8, blank=True)
    can_edit_result = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["match_number", "id"]

    def __str__(self) -> str:
        return f"{self.tournament.name} match #{self.match_number}"


class Standing(models.Model):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="standings",
    )
    pool = models.ForeignKey(
        Pool,
        on_delete=models.CASCADE,
        related_name="standings",
    )
    team = models.ForeignKey(
        "core.Team",
        on_delete=models.CASCADE,
        related_name="pool_standings",
    )
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    points = models.IntegerField(default=0)
    points_for = models.IntegerField(default=0)
    points_against = models.IntegerField(default=0)
    point_difference = models.IntegerField(default=0)
    set_ratio = models.FloatField(default=0.0)
    rank = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["pool_id", "rank", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tournament", "pool", "team"], name="uniq_standing_team_per_pool"),
        ]

    def __str__(self) -> str:
        return f"{self.tournament.name} {self.pool.name} {self.team.name}"


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
