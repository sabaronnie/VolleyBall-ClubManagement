import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def _default_expiry():
    return timezone.now() + timedelta(days=7)


def _generate_code():
    return secrets.token_urlsafe(24)


class PlayerParentInvitationStatus(models.TextChoices):
    PENDING_APPROVAL = "pending_approval", "Pending approval"
    PENDING_PARENT_RESPONSE = "pending_parent_response", "Pending parent response"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    REJECTED = "rejected", "Rejected"
    EXPIRED = "expired", "Expired"


class PlayerParentInvitation(models.Model):
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_invitations",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="requested_parent_invitations",
    )
    invited_parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_parent_invitations",
    )
    invited_email = models.EmailField()
    code = models.CharField(max_length=128, unique=True, default=_generate_code)
    status = models.CharField(
        max_length=32,
        choices=PlayerParentInvitationStatus.choices,
        default=PlayerParentInvitationStatus.PENDING_APPROVAL,
    )
    director_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_parent_invitations_as_director",
    )
    director_approved_at = models.DateTimeField(null=True, blank=True)
    coach_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_parent_invitations_as_coach",
    )
    coach_approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    invited_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(default=_default_expiry)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"], name="core_ppi_code_idx"),
            models.Index(fields=["player", "status"], name="core_ppi_player_status_idx"),
            models.Index(fields=["invited_email", "status"], name="core_ppi_email_status_idx"),
        ]

    def __str__(self):
        return f"{self.invited_email} -> {self.player_id} ({self.status})"
