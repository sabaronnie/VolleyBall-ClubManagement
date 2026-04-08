from django.apps import apps
from django.db import models


class ClubQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(memberships__user=user).distinct()


class ClubManager(models.Manager):
    def get_queryset(self):
        return ClubQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def create_club(self, *, name, director, description=""):
        club = self.create(name=name, description=description)

        club_membership_model = apps.get_model("core", "ClubMembership")
        club_membership_model.objects.assign_director(user=director, club=club)
        return club


class Club(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    objects = ClubManager()

    def __str__(self) -> str:
        return self.name
