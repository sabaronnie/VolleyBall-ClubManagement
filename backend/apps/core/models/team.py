from django.db import models


class TeamQuerySet(models.QuerySet):
    def for_club(self, club):
        return self.filter(club=club)

    def for_user(self, user):
        return self.filter(memberships__user=user).distinct()


class TeamManager(models.Manager):
    def get_queryset(self):
        return TeamQuerySet(self.model, using=self._db)

    def for_club(self, club):
        return self.get_queryset().for_club(club)

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def create_team(self, *, club, name, description=""):
        return self.create(club=club, name=name, description=description)


class Team(models.Model):
    club = models.ForeignKey(
        "core.Club",
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    objects = TeamManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["club", "name"],
                name="unique_team_name_per_club",
            )
        ]

    def __str__(self) -> str:
        return f"{self.club} - {self.name}"
