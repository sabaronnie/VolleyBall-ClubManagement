from django.conf import settings
from django.db import models


class TeamSkillCategory(models.TextChoices):
    ATTACK = "attack", "Attack"
    DEFENSE = "defense", "Defense"
    SERVE = "serve", "Serve"
    BLOCK = "block", "Block"


class CoachFeedbackStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ADDRESSED = "addressed", "Addressed"


class TeamSkillDashboardMetric(models.Model):
    """
    Coach-dashboard chart: attendance rate vs average performance score per skill bucket.
    Values are percentages in the range 0–100.
    """

    team = models.ForeignKey(
        "core.Team",
        on_delete=models.CASCADE,
        related_name="skill_dashboard_metrics",
    )
    skill_category = models.CharField(max_length=20, choices=TeamSkillCategory.choices)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2)
    average_performance = models.DecimalField(max_digits=5, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["team", "skill_category"],
                name="unique_team_skill_dashboard_metric",
            )
        ]
        ordering = ["team_id", "skill_category"]

    def __str__(self) -> str:
        return f"{self.team} {self.skill_category}"


class TeamRosterPlayerStat(models.Model):
    """Aggregated volleyball stats per player on a team (coach dashboard table)."""

    team = models.ForeignKey(
        "core.Team",
        on_delete=models.CASCADE,
        related_name="roster_player_stats",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_roster_stats",
    )
    spikes = models.PositiveIntegerField(default=0)
    blocks = models.PositiveIntegerField(default=0)
    serve_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    prior_serve_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["team", "player"],
                name="unique_team_roster_player_stat",
            )
        ]
        ordering = ["team_id", "player__first_name", "player__last_name"]

    def __str__(self) -> str:
        return f"{self.team} — {self.player}"


class TeamCoachFeedback(models.Model):
    """Coach-written feedback for a player; pending items drive the feedback-due KPI."""

    team = models.ForeignKey(
        "core.Team",
        on_delete=models.CASCADE,
        related_name="coach_feedback_entries",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coach_feedback_received",
    )
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coach_feedback_authored",
    )
    body = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=CoachFeedbackStatus.choices,
        default=CoachFeedbackStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.team} {self.player} ({self.status})"
