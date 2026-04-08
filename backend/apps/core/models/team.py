from django.db import models


class Team(models.Model):
    club = models.ForeignKey(
        "core.Club",
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["club", "name"],
                name="unique_team_name_per_club",
            )
        ]

    def __str__(self) -> str:
        return f"{self.club} - {self.name}"
