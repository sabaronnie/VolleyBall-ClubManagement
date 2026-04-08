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

    def create_club(self, *, name, director, description="", **extra_fields):
        club = self.create(name=name, description=description, **extra_fields)

        club_membership_model = apps.get_model("core", "ClubMembership")
        club_membership_model.objects.assign_director(user=director, club=club)
        return club


class Club(models.Model):
    name = models.CharField(max_length=255, unique=True)
    short_name = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    founded_year = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ClubManager()

    def __str__(self) -> str:
        return self.name
