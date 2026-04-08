from django.conf import settings
from django.db import models


class ClubRole(models.TextChoices):
    CLUB_DIRECTOR = "club_director", "Club Director"


class TeamRole(models.TextChoices):
    PLAYER = "player", "Player"
    COACH = "coach", "Coach"


class ClubMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="club_memberships",
    )
    club = models.ForeignKey(
        "core.Club",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=30, choices=ClubRole.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "club", "role"],
                name="unique_club_role_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.get_role_display()} - {self.club}"


class TeamMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    team = models.ForeignKey(
        "core.Team",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=TeamRole.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "team", "role"],
                name="unique_team_role_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.get_role_display()} - {self.team}"

