"""
EP-28: coach notifications when post-session roster attendance confirmations are incomplete.

See attendance_summary.ATTENDANCE_INCOMPLETE_RULES_TEXT for the definition of "incomplete".
Reminders are implemented as Notification rows (category attendance_incomplete) with a
training_session FK; duplicate rows per coach+session are prevented via update_or_create
and a partial unique constraint on the model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from .attendance_summary import (
    ATTENDANCE_INCOMPLETE_RULES_TEXT,
    roster_player_ids_for_team,
    session_attendance_incomplete_for_coach_reminder,
    training_session_has_ended,
)
from .models import (
    MatchPlayerStat,
    Notification,
    TeamMembership,
    TeamRole,
    TrainingSession,
    TrainingSessionConfirmation,
)


def coach_attendance_action_path(team_id: int, session_id: int) -> str:
    return f"/coach/attendance?team={team_id}&session={session_id}"


def _format_time_12h(value):
    return value.strftime("%I:%M %p").lstrip("0")


def confirmed_player_ids_for_session(session_id: int) -> set[int]:
    return set(
        TrainingSessionConfirmation.objects.filter(training_session_id=session_id).values_list(
            "player_id",
            flat=True,
        )
    )


def _match_stat_activity_filter() -> Q:
    return (
        Q(points_scored__gt=0)
        | Q(aces__gt=0)
        | Q(blocks__gt=0)
        | Q(assists__gt=0)
        | Q(errors__gt=0)
        | Q(digs__gt=0)
    )


def covered_player_ids_for_session(session: TrainingSession) -> set[int]:
    covered = confirmed_player_ids_for_session(session.id)
    if session.session_type != TrainingSession.SessionType.MATCH:
        return covered
    covered |= set(
        MatchPlayerStat.objects.filter(training_session_id=session.id)
        .filter(_match_stat_activity_filter())
        .values_list("player_id", flat=True)
    )
    return covered


def coach_users_for_team(team):
    coach_ids = TeamMembership.objects.active().filter(team=team, role=TeamRole.COACH).values_list(
        "user_id",
        flat=True,
    )
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return list(User.objects.filter(id__in=coach_ids))


def dismiss_incomplete_attendance_notifications_for_session(session_id: int) -> int:
    deleted, _ = Notification.objects.filter(
        training_session_id=session_id,
        category=Notification.Category.ATTENDANCE_INCOMPLETE,
    ).delete()
    return deleted


def sync_incomplete_attendance_notifications_for_session(
    session: TrainingSession,
    *,
    now: Optional[datetime] = None,
) -> None:
    """
    Create or refresh coach reminders, or delete them when attendance is complete / session ineligible.
    Only active team coaches receive notifications (not club directors unless they are also coaches).
    """
    now = now if now is not None else timezone.now()
    team = session.team
    roster_ids = roster_player_ids_for_team(team)
    covered_player_ids = covered_player_ids_for_session(session)

    eligible = (
        session.status != TrainingSession.Status.CANCELLED
        and training_session_has_ended(session, now=now)
        and bool(roster_ids)
    )
    incomplete = eligible and session_attendance_incomplete_for_coach_reminder(
        session,
        roster_ids,
        covered_player_ids,
    )

    if not incomplete:
        dismiss_incomplete_attendance_notifications_for_session(session.id)
        return

    missing_count = sum(1 for pid in roster_ids if pid not in covered_player_ids)
    title = f"Incomplete attendance — {team.name}"
    path = coach_attendance_action_path(team.id, session.id)
    message = (
        f"\"{session.title}\" on {session.scheduled_date.isoformat()} "
        f"({_format_time_12h(session.start_time)}-{_format_time_12h(session.end_time)}) "
        f"still needs confirmations for {missing_count} roster player(s). "
        f"Review in Team attendance: {path}"
    )

    coaches = coach_users_for_team(team)
    if not coaches:
        dismiss_incomplete_attendance_notifications_for_session(session.id)
        return

    for coach in coaches:
        Notification.objects.update_or_create(
            recipient=coach,
            training_session=session,
            category=Notification.Category.ATTENDANCE_INCOMPLETE,
            defaults={
                "team": team,
                "title": title,
                "message": message,
                "is_read": False,
                "created_by": None,
            },
        )


def sync_incomplete_attendance_notifications_for_session_id(
    session_id: int,
    *,
    now: Optional[datetime] = None,
) -> None:
    session = TrainingSession.objects.select_related("team").filter(pk=session_id).first()
    if session is None:
        return
    sync_incomplete_attendance_notifications_for_session(session, now=now)


def sweep_incomplete_attendance_reminders(*, now: Optional[datetime] = None) -> int:
    """
    Scan scheduled training sessions that might need reminders; refresh or clear notifications.
    Returns the number of sessions that were incomplete (and processed) this run.
    """
    now = now if now is not None else timezone.now()
    today = timezone.localdate()
    qs = (
        TrainingSession.objects.filter(
            status=TrainingSession.Status.SCHEDULED,
            scheduled_date__lte=today,
        )
        .select_related("team")
        .order_by("id")
    )
    incomplete_count = 0
    for session in qs.iterator(chunk_size=200):
        roster_ids = roster_player_ids_for_team(session.team)
        covered_player_ids = covered_player_ids_for_session(session)
        eligible = (
            training_session_has_ended(session, now=now)
            and bool(roster_ids)
        )
        incomplete = (
            eligible
            and session_attendance_incomplete_for_coach_reminder(
                session, roster_ids, covered_player_ids
            )
        )
        if incomplete:
            sync_incomplete_attendance_notifications_for_session(session, now=now)
            incomplete_count += 1
        else:
            dismiss_incomplete_attendance_notifications_for_session(session.id)
    return incomplete_count


__all__ = [
    "ATTENDANCE_INCOMPLETE_RULES_TEXT",
    "coach_attendance_action_path",
    "confirmed_player_ids_for_session",
    "dismiss_incomplete_attendance_notifications_for_session",
    "sweep_incomplete_attendance_reminders",
    "sync_incomplete_attendance_notifications_for_session",
    "sync_incomplete_attendance_notifications_for_session_id",
]
