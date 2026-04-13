from django.conf import settings
from django.db import models

from .user import AssignedAccountRole


class UserAccountRole(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_role_assignment",
    )
    role = models.CharField(max_length=20, choices=AssignedAccountRole.choices)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
        ]

