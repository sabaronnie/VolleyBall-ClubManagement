from django.conf import settings
from django.db import models


class PlayerWeeklySkillMetric(models.Model):
    """
    Coach-recorded weekly skill scores for a player on a specific team (0–100 scale).
    Powers member/parent dashboard progress charts (Attack / Defense / Serve).
    """

    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_skill_metrics",
    )
    team = models.ForeignKey(
        "core.Team",
        on_delete=models.CASCADE,
        related_name="player_weekly_skill_metrics",
    )
    week_start = models.DateField(
        help_text="Monday (ISO week start) for this data point.",
    )
    attack = models.DecimalField(max_digits=5, decimal_places=2)
    defense = models.DecimalField(max_digits=5, decimal_places=2)
    serve = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["player", "team", "week_start"],
                name="unique_player_team_week_skill_metric",
            )
        ]
        ordering = ["player_id", "team_id", "week_start"]

    def __str__(self) -> str:
        return f"{self.player_id} / {self.team_id} / {self.week_start}"
