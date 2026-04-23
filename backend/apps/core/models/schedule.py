from django.conf import settings
from django.db import models


class TeamScheduleEntry(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    team = models.ForeignKey(
        "core.Team",
        on_delete=models.CASCADE,
        related_name="schedule_entries",
    )
    activity_name = models.CharField(max_length=255)
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_team_schedule_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["weekday", "start_time", "end_time", "activity_name"]

    def __str__(self) -> str:
        return f"{self.team} - {self.activity_name} ({self.get_weekday_display()})"


class TrainingSession(models.Model):
    class SessionType(models.TextChoices):
        TRAINING = "training", "Training"
        MATCH = "match", "Match"

    class MatchType(models.TextChoices):
        FRIENDLY = "friendly", "Friendly"
        LEAGUE = "league", "League"
        TOURNAMENT = "tournament", "Tournament"
        SCRIMMAGE = "scrimmage", "Scrimmage"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CANCELLED = "cancelled", "Cancelled"

    team = models.ForeignKey(
        "core.Team",
        on_delete=models.CASCADE,
        related_name="training_sessions",
    )
    title = models.CharField(max_length=255)
    session_type = models.CharField(
        max_length=20,
        choices=SessionType.choices,
        default=SessionType.TRAINING,
    )
    scheduled_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=255, blank=True)
    opponent = models.CharField(max_length=255, blank=True)
    match_type = models.CharField(
        max_length=20,
        choices=MatchType.choices,
        blank=True,
    )
    notes = models.TextField(blank=True)
    notify_players = models.BooleanField(default=True)
    notify_parents = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_training_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_date", "start_time", "title"]

    def __str__(self) -> str:
        return f"{self.team} - {self.title} ({self.scheduled_date.isoformat()})"


class TrainingSessionConfirmation(models.Model):
    training_session = models.ForeignKey(
        "core.TrainingSession",
        on_delete=models.CASCADE,
        related_name="confirmations",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_session_confirmations",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_training_session_confirmations",
    )
    confirmed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["training_session", "player"],
                name="unique_training_session_confirmation_per_player",
            )
        ]
        ordering = ["player__first_name", "player__last_name", "player__email"]

    def __str__(self) -> str:
        return f"{self.training_session} - {self.player}"


class MatchPlayerStat(models.Model):
    training_session = models.ForeignKey(
        "core.TrainingSession",
        on_delete=models.CASCADE,
        related_name="match_player_stats",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_player_stats",
    )
    points_scored = models.PositiveIntegerField(default=0)
    aces = models.PositiveIntegerField(default=0)
    blocks = models.PositiveIntegerField(default=0)
    assists = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    digs = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_match_player_stats",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["training_session", "player"],
                name="unique_match_stat_per_session_player",
            )
        ]
        ordering = ["player__first_name", "player__last_name", "player__email"]

    def __str__(self) -> str:
        return f"{self.training_session} - {self.player} stats"
