from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone

from .models import AssignedAccountRole, ClubMembership, ClubRole, ParentPlayerRelation, TeamMembership, TeamRole


JWT_ALGORITHM = "HS256"


def _canonical_app_role(user) -> str:
    if ClubMembership.objects.active().filter(user=user, role=ClubRole.CLUB_DIRECTOR).exists():
        return AssignedAccountRole.DIRECTOR
    if TeamMembership.objects.active().filter(user=user, role=TeamRole.COACH).exists():
        return AssignedAccountRole.COACH
    if TeamMembership.objects.active().filter(user=user, role=TeamRole.PLAYER).exists():
        return AssignedAccountRole.PLAYER
    if ParentPlayerRelation.objects.approved().filter(parent=user).exists():
        return AssignedAccountRole.PARENT
    return "user"


def generate_auth_token(user):
    now = timezone.now()
    exp = now + timedelta(minutes=getattr(settings, "JWT_ACCESS_TOKEN_MINUTES", 60))
    payload = {
        "user_id": user.pk,
        "user_role": _canonical_app_role(user),
        "email": user.email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_auth_token(token):
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "user_id", "user_role"]},
    )

