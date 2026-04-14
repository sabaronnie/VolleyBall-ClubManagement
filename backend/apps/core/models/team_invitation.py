import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from .membership import TeamRole


def _default_expiry():
    return timezone.now() + timedelta(days=7)


def _generate_code():
    return secrets.token_urlsafe(24)


class TeamInvitationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    EXPIRED = "expired", "Expired"


class TeamInvitation(models.Model):
    team = models.ForeignKey("core.Team", on_delete=models.CASCADE, related_name="invitations")
    invited_email = models.EmailField()
    role = models.CharField(max_length=20, choices=TeamRole.choices, default=TeamRole.PLAYER)
    code = models.CharField(max_length=128, unique=True, default=_generate_code)
    status = models.CharField(
        max_length=20,
        choices=TeamInvitationStatus.choices,
        default=TeamInvitationStatus.PENDING,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_team_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_expiry)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"], name="core_teamin_code_4ddd0f_idx"),
            models.Index(fields=["team", "invited_email", "status"], name="core_teamin_team_id_d01703_idx"),
        ]

    def __str__(self):
        return f"{self.invited_email} -> {self.team.name} ({self.status})"
