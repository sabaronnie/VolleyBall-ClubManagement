from django.conf import settings
from django.db import models


class PlayerAccessPolicyQuerySet(models.QuerySet):
    def for_player(self, player):
        return self.filter(player=player)


class PlayerAccessPolicyManager(models.Manager):
    def get_queryset(self):
        return PlayerAccessPolicyQuerySet(self.model, using=self._db)

    def for_player(self, player):
        return self.get_queryset().for_player(player)

    def get_or_create_for_player(self, *, player):
        policy, _ = self.get_or_create(player=player)
        return policy


class PlayerAccessPolicy(models.Model):
    FEATURE_FIELD_MAP = {
        "confirm_attendance": "can_self_confirm_attendance",
        "make_payments": "can_self_make_payments",
        "submit_absence_reasons": "can_self_submit_absence_reasons",
        "approve_schedule_confirmations": "can_self_approve_schedule_confirmations",
        "update_emergency_contact": "can_self_update_emergency_contact",
    }

    player = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_policy",
    )
    is_parent_managed = models.BooleanField(default=False)
    can_self_confirm_attendance = models.BooleanField(default=True)
    can_self_make_payments = models.BooleanField(default=True)
    can_self_submit_absence_reasons = models.BooleanField(default=True)
    can_self_approve_schedule_confirmations = models.BooleanField(default=True)
    can_self_update_emergency_contact = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlayerAccessPolicyManager()

    def allows_player(self, feature: str) -> bool:
        try:
            field_name = self.FEATURE_FIELD_MAP[feature]
        except KeyError as exc:
            raise ValueError(f"Unsupported player access feature: {feature}") from exc

        return bool(getattr(self, field_name))

    def __str__(self) -> str:
        return f"Access Policy - {self.player}"
