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

    def create_team(self, *, club, name, description="", **extra_fields):
        return self.create(club=club, name=name, description=description, **extra_fields)


class Team(models.Model):
    class Gender(models.TextChoices):
        BOYS = "boys", "Boys"
        GIRLS = "girls", "Girls"
        MIXED = "mixed", "Mixed"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    club = models.ForeignKey(
        "core.Club",
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    season = models.CharField(max_length=50, blank=True)
    age_group = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=20, choices=Gender.choices, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    home_venue = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
