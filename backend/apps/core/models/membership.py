from django.utils import timezone
from django.conf import settings
from django.db import models


class ClubRole(models.TextChoices):
    CLUB_DIRECTOR = "club_director", "Club Director"


class TeamRole(models.TextChoices):
    PLAYER = "player", "Player"
    COACH = "coach", "Coach"


class ClubMembershipQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

    def for_user(self, user):
        return self.filter(user=user)

    def for_club(self, club):
        return self.filter(club=club)

    def directors(self):
        return self.filter(role=ClubRole.CLUB_DIRECTOR)


class ClubMembershipManager(models.Manager):
    def get_queryset(self):
        return ClubMembershipQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def inactive(self):
        return self.get_queryset().inactive()

    def assign_director(self, *, user, club):
        membership, _ = self.update_or_create(
            user=user,
            club=club,
            role=ClubRole.CLUB_DIRECTOR,
            defaults={
                "is_active": True,
                "left_at": None,
            },
        )
        return membership

    def deactivate(self, membership):
        membership.is_active = False
        membership.left_at = timezone.now()
        membership.save(update_fields=["is_active", "left_at"])
        return membership


class TeamMembershipQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)

    def for_user(self, user):
        return self.filter(user=user)

    def for_team(self, team):
        return self.filter(team=team)

    def players(self):
        return self.filter(role=TeamRole.PLAYER)

    def coaches(self):
        return self.filter(role=TeamRole.COACH)

    def captains(self):
        return self.filter(is_captain=True)


class TeamMembershipManager(models.Manager):
    def get_queryset(self):
        return TeamMembershipQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def inactive(self):
        return self.get_queryset().inactive()

    def add_member(self, *, user, team, role, is_captain=False):
        membership, _ = self.update_or_create(
            user=user,
            team=team,
            defaults={
                "role": role,
                "is_captain": is_captain,
                "is_active": True,
                "left_at": None,
            },
        )
        return membership

    def deactivate(self, membership):
        membership.is_active = False
        membership.left_at = timezone.now()
        membership.save(update_fields=["is_active", "left_at"])
        return membership


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
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(blank=True, null=True)

    objects = ClubMembershipManager()

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
    is_captain = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(blank=True, null=True)

    objects = TeamMembershipManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "team"],
                name="unique_team_membership_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.get_role_display()} - {self.team}"
