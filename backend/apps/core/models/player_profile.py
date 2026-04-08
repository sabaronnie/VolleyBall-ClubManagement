from django.conf import settings
from django.db import models


class PlayerProfileQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)

    def with_position(self, position):
        return self.filter(primary_position=position)


class PlayerProfileManager(models.Manager):
    def get_queryset(self):
        return PlayerProfileQuerySet(self.model, using=self._db)

    def create_profile(self, *, user, jersey_number=None, primary_position="", notes=""):
        return self.create(
            user=user,
            jersey_number=jersey_number,
            primary_position=primary_position,
            notes=notes,
        )


class PlayerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="player_profile",
    )
    jersey_number = models.PositiveSmallIntegerField(blank=True, null=True)
    primary_position = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    objects = PlayerProfileManager()

    def __str__(self) -> str:
        return f"Player Profile - {self.user}"
