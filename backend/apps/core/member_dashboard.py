"""
Aggregated parent/player dashboard payload (DB-backed only).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .attendance_summary import format_person_name
from .coach_dashboard import _format_time_12h
from .models import (
    MatchPlayerStat,
    Notification,
    ParentPlayerRelation,
    PlayerAccessPolicy,
    PlayerParentInvitation,
    PlayerParentInvitationStatus,
    PlayerFeeRecord,
    PlayerWeeklySkillMetric,
    TeamMembership,
    TeamRole,
    TrainingSession,
    TrainingSessionConfirmation,
)
from .payment_views import _family_overall_status, _serialize_fee_record
from .permissions import (
    can_parent_manage_player_access,
    can_player_update_own_emergency_contact,
    is_user_adult,
)

User = get_user_model()


def _age_on_today(dob: Optional[date]) -> Optional[int]:
    if dob is None:
        return None
    today = timezone.localdate()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age


def _approved_child_ids_for_parent(parent: User) -> list[int]:
    return list(
        ParentPlayerRelation.objects.approved()
        .filter(parent=parent)
        .values_list("player_id", flat=True)
        .order_by("player_id")
    )


def _viewer_is_active_player(viewer: User) -> bool:
    return TeamMembership.objects.active().filter(user=viewer, role=TeamRole.PLAYER).exists()


def resolve_focus_player(
    viewer: User,
    for_player_id: Optional[int],
) -> tuple[Optional[User], Optional[str]]:
    """
    Returns (focus_user, error_code).
    error_code: 'forbidden' | 'not_a_player' | None
    """
    child_ids = _approved_child_ids_for_parent(viewer)
    is_player = _viewer_is_active_player(viewer)

    if for_player_id is not None:
        if for_player_id == viewer.id:
            if not is_player:
                return None, "not_a_player"
            return viewer, None
        if for_player_id in child_ids:
            return User.objects.get(pk=for_player_id), None
        return None, "forbidden"

    if is_player:
        return viewer, None
    if child_ids:
        return User.objects.get(pk=child_ids[0]), None
    return None, None


def _serialize_child_option(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


def _player_team_memberships(focus: User) -> list[TeamMembership]:
    return list(
        TeamMembership.objects.active()
        .filter(user=focus, role=TeamRole.PLAYER)
        .select_related("team", "team__club")
        .order_by("team__club__name", "team__name", "team_id")
    )


def _pick_progress_team_id(focus: User, memberships: list[TeamMembership]) -> Optional[int]:
    if not memberships:
        return None
    team_ids = [m.team_id for m in memberships]
    latest = (
        PlayerWeeklySkillMetric.objects.filter(player=focus, team_id__in=team_ids)
        .order_by("-week_start", "-id")
        .values_list("team_id", flat=True)
        .first()
    )
    if latest is not None:
        return int(latest)
    return memberships[0].team_id


def _coach_names_for_team(team_id: int) -> list[str]:
    coaches = (
        TeamMembership.objects.active()
        .filter(team_id=team_id, role=TeamRole.COACH)
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "user__email")
    )
    return [format_person_name(m.user) for m in coaches]


def _next_session_for_player(focus: User, memberships: list[TeamMembership]) -> Optional[TrainingSession]:
    if not memberships:
        return None
    team_ids = [m.team_id for m in memberships]
    today = timezone.localdate()
    now_t = timezone.localtime().time()

    qs = (
        TrainingSession.objects.filter(team_id__in=team_ids)
        .exclude(status=TrainingSession.Status.CANCELLED)
        .filter(
            Q(scheduled_date__gt=today)
            | Q(scheduled_date=today, end_time__gte=now_t)
        )
        .select_related("team", "team__club")
        .order_by("scheduled_date", "start_time", "id")
    )
    return qs.first()


def _progress_payload(focus: User, progress_team_id: Optional[int]) -> dict[str, Any]:
    if progress_team_id is None:
        return {
            "team_id": None,
            "weeks": [],
            "summary": {"attack": None, "defense": None, "serve": None},
            "has_weekly_metrics": False,
        }

    today = timezone.localdate()
    horizon_start = today - timedelta(weeks=12)
    rows = list(
        PlayerWeeklySkillMetric.objects.filter(
            player=focus,
            team_id=progress_team_id,
            week_start__gte=horizon_start,
        ).order_by("week_start", "id")
    )
    weeks_out: list[dict[str, Any]] = []
    for row in rows:
        weeks_out.append(
            {
                "week_start": row.week_start.isoformat(),
                "week_label": row.week_start.strftime("%b %d"),
                "attack": float(row.attack),
                "defense": float(row.defense),
                "serve": float(row.serve),
            }
        )
    summary = {"attack": None, "defense": None, "serve": None}
    if rows:
        last = rows[-1]
        summary = {
            "attack": float(last.attack),
            "defense": float(last.defense),
            "serve": float(last.serve),
        }
        return {
            "team_id": progress_team_id,
            "weeks": weeks_out,
            "summary": summary,
            "has_weekly_metrics": True,
        }

    # Fallback: build simple development trend from recorded match stats when
    # explicit weekly coach metrics are not entered yet.
    stat_rows = list(
        MatchPlayerStat.objects.filter(player=focus)
        .filter(
            Q(training_session__team_id=progress_team_id)
            | Q(
                training_session__opponent_team_id=progress_team_id,
                training_session__match_request_status=TrainingSession.MatchRequestStatus.ACCEPTED,
            )
        )
        .filter(training_session__session_type=TrainingSession.SessionType.MATCH)
        .exclude(training_session__status=TrainingSession.Status.CANCELLED)
        .filter(training_session__scheduled_date__gte=horizon_start)
        .select_related("training_session")
        .order_by("training_session__scheduled_date", "training_session__id")
    )

    if not stat_rows:
        return {
            "team_id": progress_team_id,
            "weeks": [],
            "summary": summary,
            "has_weekly_metrics": False,
        }

    weekly_buckets: dict[date, dict[str, float]] = {}
    for row in stat_rows:
        session_date = row.training_session.scheduled_date
        week_start = session_date - timedelta(days=session_date.weekday())
        bucket = weekly_buckets.setdefault(
            week_start,
            {
                "attack_raw": 0.0,
                "defense_raw": 0.0,
                "aces": 0.0,
                "errors": 0.0,
            },
        )
        points = float(row.points_scored or 0)
        aces = float(row.aces or 0)
        blocks = float(row.blocks or 0)
        digs = float(row.digs or 0)
        errors = float(row.errors or 0)
        bucket["attack_raw"] += points + (2.0 * aces) + (2.0 * blocks)
        bucket["defense_raw"] += digs + blocks
        bucket["aces"] += aces
        bucket["errors"] += errors

    weeks_out = []
    for week_start in sorted(weekly_buckets.keys()):
        bucket = weekly_buckets[week_start]
        serve_attempts = bucket["aces"] + bucket["errors"]
        serve_score = (bucket["aces"] / serve_attempts * 100.0) if serve_attempts > 0 else 0.0
        weeks_out.append(
            {
                "week_start": week_start.isoformat(),
                "week_label": week_start.strftime("%b %d"),
                "attack": min(100.0, bucket["attack_raw"] * 5.0),
                "defense": min(100.0, bucket["defense_raw"] * 8.0),
                "serve": max(0.0, min(100.0, serve_score)),
            }
        )

    last = weeks_out[-1]
    return {
        "team_id": progress_team_id,
        "weeks": weeks_out,
        "summary": {
            "attack": float(last["attack"]),
            "defense": float(last["defense"]),
            "serve": float(last["serve"]),
        },
        "has_weekly_metrics": True,
    }


def _linked_parent_rows_for_player(player: User) -> list[dict[str, Any]]:
    rows = (
        ParentPlayerRelation.objects.approved()
        .filter(player=player)
        .select_related("parent")
        .order_by("parent__first_name", "parent__last_name", "parent__email", "id")
    )
    return [
        {
            "id": rel.parent_id,
            "email": rel.parent.email,
            "first_name": rel.parent.first_name,
            "last_name": rel.parent.last_name,
            "is_legal_guardian": rel.is_legal_guardian,
        }
        for rel in rows
    ]


def _pending_parent_invites_for_player(player: User) -> list[dict[str, Any]]:
    pending_relations = (
        ParentPlayerRelation.objects.pending()
        .filter(player=player)
        .select_related("parent")
        .order_by("-id")
    )
    invites = (
        PlayerParentInvitation.objects.filter(
            player=player,
            status__in=[
                PlayerParentInvitationStatus.PENDING_APPROVAL,
                PlayerParentInvitationStatus.PENDING_PARENT_RESPONSE,
            ],
        )
        .order_by("-created_at", "-id")
    )
    out: list[dict[str, Any]] = []
    for rel in pending_relations:
        out.append(
            {
                "id": f"relation-{rel.id}",
                "email": rel.parent.email,
                "status": "pending_parent_link",
                "director_approved": False,
                "coach_approved": False,
                "waiting_for": ["director"],
                "invited_at": None,
                "expires_at": None,
            }
        )
    for invite in invites:
        waiting_for = []
        if invite.status == PlayerParentInvitationStatus.PENDING_APPROVAL:
            if invite.director_approved_at is None:
                waiting_for.append("director")
            if invite.coach_approved_at is None:
                waiting_for.append("coach")
        out.append(
            {
                "id": invite.id,
                "email": invite.invited_email,
                "status": invite.status,
                "director_approved": invite.director_approved_at is not None,
                "coach_approved": invite.coach_approved_at is not None,
                "waiting_for": waiting_for,
                "invited_at": invite.invited_at.isoformat() if invite.invited_at else None,
                "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
            }
        )
    return out


def _serialize_player_access_policy(policy: Optional[PlayerAccessPolicy]) -> dict[str, Any]:
    if policy is None:
        return {
            "is_parent_managed": False,
            "can_self_confirm_attendance": True,
            "can_self_make_payments": True,
            "can_self_update_emergency_contact": True,
        }

    return {
        "is_parent_managed": policy.is_parent_managed,
        "can_self_confirm_attendance": policy.can_self_confirm_attendance,
        "can_self_make_payments": policy.can_self_make_payments,
        "can_self_update_emergency_contact": policy.can_self_update_emergency_contact,
    }


def _can_update_focus_emergency_contact(*, viewer: User, focus: User) -> bool:
    if viewer == focus:
        is_player = TeamMembership.objects.active().filter(user=focus, role=TeamRole.PLAYER).exists()
        return can_player_update_own_emergency_contact(focus) if is_player else True

    return ParentPlayerRelation.objects.approved().filter(parent=viewer, player=focus).exists()


def build_member_hub_dashboard_payload(
    viewer: User,
    *,
    for_player_id: Optional[int],
) -> tuple[dict[str, Any], int]:
    child_ids = _approved_child_ids_for_parent(viewer)
    children_users = list(User.objects.filter(id__in=child_ids).order_by("first_name", "last_name", "id"))
    available_children = [_serialize_child_option(u) for u in children_users]

    focus, err = resolve_focus_player(viewer, for_player_id)
    if err == "forbidden":
        return {"errors": {"for_player_id": "You cannot view this player's dashboard."}}, 403
    if err == "not_a_player":
        return {"errors": {"for_player_id": "That account is not a player roster member."}}, 400

    base: dict[str, Any] = {
        "viewer": {
            "id": viewer.id,
            "email": viewer.email,
            "first_name": viewer.first_name,
            "last_name": viewer.last_name,
        },
        "available_children": available_children,
        "focus_player": None,
        "profile": None,
        "payment": None,
        "progress": None,
        "club_summary": None,
        "parent_permissions": None,
        "quick_actions": {
            "confirm_attendance_path": "/parent/attendance"
            if child_ids and not _viewer_is_active_player(viewer)
            else "/player/attendance",
            "confirm_attendance_mode": "parent" if child_ids and not _viewer_is_active_player(viewer) else "player",
            "development_progress_path": "/teams",
            "messages_action": "dispatch_event",
            "messages_event_name": "vc-open-notifications",
        },
        "notifications": {
            "unread_count": Notification.objects.filter(recipient=viewer, is_read=False).count(),
        },
    }

    if focus is None:
        return base, 200

    memberships = _player_team_memberships(focus)
    progress_team_id = _pick_progress_team_id(focus, memberships)

    primary_membership = next((m for m in memberships if m.team_id == progress_team_id), None)
    if primary_membership is None and memberships:
        primary_membership = memberships[0]

    coach_names = _coach_names_for_team(primary_membership.team_id) if primary_membership else []

    base["focus_player"] = {
        "id": focus.id,
        "email": focus.email,
        "first_name": focus.first_name,
        "last_name": focus.last_name,
        "date_of_birth": focus.date_of_birth.isoformat() if focus.date_of_birth else None,
        "emergency_contact": focus.emergency_contact,
        "can_update_emergency_contact": _can_update_focus_emergency_contact(
            viewer=viewer,
            focus=focus,
        ),
    }
    base["profile"] = {
        "display_name": format_person_name(focus),
        "age_years": _age_on_today(focus.date_of_birth),
        "avatar_url": None,
        "team": None if not primary_membership
        else {
            "id": primary_membership.team.id,
            "name": primary_membership.team.name,
            "club_id": primary_membership.team.club_id,
            "club_name": primary_membership.team.club.name if primary_membership.team.club_id else "",
        },
        "coach_names": coach_names,
        "coach_display": ", ".join(coach_names) if coach_names else None,
    }
    linked_parents = _linked_parent_rows_for_player(focus)
    pending_parent_invites = _pending_parent_invites_for_player(focus)
    base["parent_access"] = {
        "can_manage": viewer.id == focus.id,
        "max_parents": 2,
        "linked_parents": linked_parents,
        "pending_requests": pending_parent_invites,
        "minor_locked": not is_user_adult(focus),
    }
    if can_parent_manage_player_access(viewer, focus):
        policy = PlayerAccessPolicy.objects.for_player(focus).first()
        base["parent_permissions"] = {
            "can_manage": True,
            "policy": _serialize_player_access_policy(policy),
            "reason": None,
            "message": "",
        }
    elif focus.id in child_ids and is_user_adult(focus):
        base["parent_permissions"] = {
            "can_manage": False,
            "policy": None,
            "reason": "adult_player",
            "message": (
                "This player is an adult now, so parent-managed permissions no "
                "longer apply and can no longer be modified."
            ),
        }
    else:
        base["parent_permissions"] = {
            "can_manage": False,
            "policy": None,
            "reason": None,
            "message": "",
        }

    fee_lines = list(
        PlayerFeeRecord.objects.filter(player=focus)
        .select_related("player", "team", "club")
        .order_by("-due_date", "-id")
    )
    serialized_lines = [_serialize_fee_record(r) for r in fee_lines]
    active = [r for r in fee_lines if r.remaining() > Decimal("0")]
    total_remaining = sum((r.remaining() for r in active), Decimal("0"))
    currency = active[0].currency if active else (fee_lines[0].currency if fee_lines else "USD")
    base["payment"] = {
        "currency": currency,
        "amount_due": float(total_remaining),
        "overall_status": _family_overall_status(fee_lines),
        "open_item_count": len(active),
        "fee_lines": serialized_lines[:12],
        "pay_path": "/my-fees",
    }

    base["progress"] = _progress_payload(focus, progress_team_id)

    next_sess = _next_session_for_player(focus, memberships)
    if next_sess:
        confirmed = TrainingSessionConfirmation.objects.filter(
            training_session=next_sess,
            player=focus,
        ).exists()
        start_disp = _format_time_12h(next_sess.start_time)
        base["club_summary"] = {
            "session_id": next_sess.id,
            "title": next_sess.title,
            "team_id": next_sess.team_id,
            "team_name": next_sess.team.name,
            "club_name": next_sess.team.club.name if next_sess.team.club_id else "",
            "session_type": next_sess.session_type,
            "session_type_label": next_sess.get_session_type_display(),
            "scheduled_date": next_sess.scheduled_date.isoformat(),
            "date_display": next_sess.scheduled_date.strftime("%A, %b %d, %Y"),
            "start_time_24h": next_sess.start_time.strftime("%H:%M"),
            "start_time_display": start_disp,
            "location": next_sess.location or "",
            "needs_confirmation": not confirmed
            and next_sess.status != TrainingSession.Status.CANCELLED,
        }
    else:
        base["club_summary"] = None

    if child_ids and not _viewer_is_active_player(viewer):
        base["quick_actions"]["confirm_attendance_path"] = "/parent/attendance"
        base["quick_actions"]["confirm_attendance_mode"] = "parent"
    else:
        base["quick_actions"]["confirm_attendance_path"] = "/player/attendance"
        base["quick_actions"]["confirm_attendance_mode"] = "player"

    return base, 200
