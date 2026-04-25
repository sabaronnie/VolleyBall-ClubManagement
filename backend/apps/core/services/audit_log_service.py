from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from apps.core.models import ParentPlayerRelation, TeamMembership, TeamRole
from apps.core.permissions import is_any_club_director
from apps.core.repositories.audit_log_repository import AuditLogRepository


def _resolve_user_role(user) -> str:
    if user is None:
        return ""
    if getattr(user, "is_staff", False):
        return "staff"
    if is_any_club_director(user):
        return "director"
    if TeamMembership.objects.active().filter(user=user, role=TeamRole.COACH).exists():
        return "coach"
    if TeamMembership.objects.active().filter(user=user, role=TeamRole.PLAYER).exists():
        return "player"
    if ParentPlayerRelation.objects.approved().filter(parent=user).exists():
        return "parent"
    return "user"


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    return value


class AuditLogService:
    @staticmethod
    def log_action(
        *,
        user,
        action_type,
        entity_type,
        entity_id,
        old_value=None,
        new_value=None,
    ):
        return AuditLogRepository.create(
            user=user,
            user_role=_resolve_user_role(user),
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=_json_safe(old_value) if old_value is not None else None,
            new_value=_json_safe(new_value) if new_value is not None else None,
        )
