"""
Centralized attendance aggregation for training sessions (EP-27).

All dashboard, analytics, and summary endpoints should derive counts and rates from
this module so status rules stay consistent with parent history (EP-23), coach
session views (EP-25), and coach trends (EP-26).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

from django.utils import timezone

from .models import (
    Club,
    Team,
    TeamMembership,
    TeamRole,
    TrainingSession,
    TrainingSessionConfirmation,
)

# Human-readable rules for API consumers (keep in sync with attendance_status + build logic).
CALCULATION_SUMMARY_TEXT = (
    "Cancelled sessions are excluded from every statistic. "
    "Attendance percentage uses only sessions with scheduled_date strictly before today "
    "in the viewer's local timezone: a confirmation counts as present; no confirmation "
    "counts as absent. Sessions on today or in the future are excluded from the "
    "percentage denominator; unconfirmed future/today sessions count as pending. "
    "Confirmed future/today sessions appear as upcoming confirmed but still do not "
    "affect the closed-session rate."
)


def attendance_status(session: TrainingSession, is_confirmed: bool) -> tuple[str, str]:
    """Map session + confirmation to a stable status code and label."""
    if session.status == TrainingSession.Status.CANCELLED:
        return "cancelled", "Cancelled"
    if is_confirmed:
        return "present", "Present"
    today = timezone.localdate()
    if session.scheduled_date >= today:
        return "pending", "Pending"
    return "absent", "Absent"


def format_person_name(user) -> str:
    return f"{user.first_name} {user.last_name}".strip() or user.email


def serialize_team_brief(team: Team) -> dict[str, Any]:
    return {
        "id": team.id,
        "club_id": team.club_id,
        "club_name": team.club.name,
        "name": team.name,
        "short_name": team.short_name,
        "description": team.description,
        "season": team.season,
        "age_group": team.age_group,
        "gender": team.gender,
        "status": team.status,
        "home_venue": team.home_venue,
        "notes": team.notes,
    }


@dataclass
class TeamAttendanceScope:
    today: date
    start_date: date
    end_date: date
    last_n_sessions: Optional[int]
    team: Team
    sessions: list[TrainingSession]
    session_ids: list[int]
    closed_sessions: list[TrainingSession]
    sessions_for_players: list[TrainingSession]
    closed_session_ids: set[int]
    conf_pairs: set[tuple[int, int]]
    player_memberships: list[TeamMembership]


def prepare_team_attendance_scope(
    team: Team,
    *,
    start_date: date,
    end_date: date,
    last_n_sessions: Optional[int],
) -> TeamAttendanceScope:
    today = timezone.localdate()

    sessions_qs = (
        TrainingSession.objects.filter(team=team)
        .exclude(status=TrainingSession.Status.CANCELLED)
        .filter(scheduled_date__gte=start_date, scheduled_date__lte=end_date)
        .order_by("scheduled_date", "start_time", "id")
    )
    sessions = list(sessions_qs)
    session_ids = [s.id for s in sessions]

    player_memberships = list(
        TeamMembership.objects.active()
        .filter(team=team, role=TeamRole.PLAYER)
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "user__email")
    )

    conf_pairs: set[tuple[int, int]] = set()
    if session_ids:
        conf_pairs = set(
            TrainingSessionConfirmation.objects.filter(training_session_id__in=session_ids).values_list(
                "training_session_id",
                "player_id",
            )
        )

    closed_sessions = [s for s in sessions if s.scheduled_date < today]
    if last_n_sessions is not None and last_n_sessions > 0:
        closed_sessions = sorted(
            closed_sessions,
            key=lambda s: (s.scheduled_date, s.start_time, s.id),
            reverse=True,
        )[:last_n_sessions]
        closed_sessions.sort(key=lambda s: (s.scheduled_date, s.start_time, s.id))
        closed_session_ids = {s.id for s in closed_sessions}
        sessions_for_players = [s for s in sessions if s.id in closed_session_ids or s.scheduled_date >= today]
    else:
        sessions_for_players = sessions
        closed_session_ids = {s.id for s in closed_sessions}

    return TeamAttendanceScope(
        today=today,
        start_date=start_date,
        end_date=end_date,
        last_n_sessions=last_n_sessions,
        team=team,
        sessions=sessions,
        session_ids=session_ids,
        closed_sessions=closed_sessions,
        sessions_for_players=sessions_for_players,
        closed_session_ids=closed_session_ids,
        conf_pairs=conf_pairs,
        player_memberships=player_memberships,
    )


def classify_scope(scope: TeamAttendanceScope, session: TrainingSession, player_id: int) -> str:
    is_confirmed = (session.id, player_id) in scope.conf_pairs
    return attendance_status(session, is_confirmed)[0]


def session_roster_summary(
    session: TrainingSession,
    player_memberships: list[TeamMembership],
    conf_pairs: Optional[set[tuple[int, int]]] = None,
) -> dict[str, int]:
    """Per-session counts for coach/director roster (EP-25); excludes cancelled from rate-relevant slots."""
    if conf_pairs is None:
        conf_pairs = set(
            TrainingSessionConfirmation.objects.filter(training_session_id=session.id).values_list(
                "training_session_id",
                "player_id",
            )
        )

    def _count(code: str) -> int:
        n = 0
        for m in player_memberships:
            is_confirmed = (session.id, m.user_id) in conf_pairs
            if attendance_status(session, is_confirmed)[0] == code:
                n += 1
        return n

    return {
        "roster_size": len(player_memberships),
        "present_count": _count("present"),
        "pending_count": _count("pending"),
        "absent_count": _count("absent"),
        "cancelled_count": _count("cancelled"),
    }


def team_closed_player_slot_totals(scope: TeamAttendanceScope) -> tuple[int, int]:
    """Sum (present_slots, closed_slots) across roster × closed sessions in scope."""
    attended = 0
    closed = 0
    for membership in scope.player_memberships:
        player_id = membership.user_id
        for session in scope.closed_sessions:
            code = classify_scope(scope, session, player_id)
            if code == "present":
                attended += 1
                closed += 1
            elif code == "absent":
                closed += 1
    return attended, closed


def build_player_row(scope: TeamAttendanceScope, membership: TeamMembership) -> dict[str, Any]:
    player = membership.user
    attended = absent = pending = upcoming_confirmed = 0
    sessions_non_cancelled = 0
    for session in scope.sessions_for_players:
        if session.status == TrainingSession.Status.CANCELLED:
            continue
        sessions_non_cancelled += 1
        code = classify_scope(scope, session, player.id)
        if session.scheduled_date < scope.today:
            if code == "present":
                attended += 1
            elif code == "absent":
                absent += 1
        elif code == "pending":
            pending += 1
        elif code == "present":
            upcoming_confirmed += 1

    counted = attended + absent
    rate = (100.0 * attended / counted) if counted else None

    total_attended_slots = 0
    total_closed_slots = 0
    for session in scope.closed_sessions:
        code = classify_scope(scope, session, player.id)
        if code == "present":
            total_attended_slots += 1
            total_closed_slots += 1
        elif code == "absent":
            total_closed_slots += 1

    if rate is None:
        flag = "insufficient_data"
    elif counted < 2:
        flag = "insufficient_data"
    elif rate < 65.0:
        flag = "low"
    elif rate >= 85.0:
        flag = "high"
    else:
        flag = "medium"

    return {
        "player_id": player.id,
        "player_name": format_person_name(player),
        "sessions_in_date_range": sessions_non_cancelled,
        "sessions_counted_for_rate": counted,
        "attended_sessions": attended,
        "absent_sessions": absent,
        "pending_sessions": pending,
        "upcoming_confirmed_sessions": upcoming_confirmed,
        "attendance_rate_percent": None if rate is None else round(rate, 2),
        "engagement_flag": flag,
        "_total_attended_slots": total_attended_slots,
        "_total_closed_slots": total_closed_slots,
    }


def build_team_attendance_analytics(
    team: Team,
    *,
    start_date: date,
    end_date: date,
    grouping: str,
    last_n_sessions: Optional[int],
) -> dict[str, Any]:
    """
    EP-26 payload: per-player metrics, optional week/session trend, team average.
    """
    scope = prepare_team_attendance_scope(
        team,
        start_date=start_date,
        end_date=end_date,
        last_n_sessions=last_n_sessions,
    )

    players_out = []
    total_attended_slots = 0
    total_closed_slots = 0

    for membership in scope.player_memberships:
        row = build_player_row(scope, membership)
        total_attended_slots += row.pop("_total_attended_slots")
        total_closed_slots += row.pop("_total_closed_slots")
        players_out.append(row)

    team_avg = (100.0 * total_attended_slots / total_closed_slots) if total_closed_slots else None

    trend: list[dict[str, Any]] = []
    grouping = (grouping or "week").strip().lower()
    if grouping not in ("week", "session"):
        grouping = "week"

    if grouping == "session":
        for session in scope.closed_sessions:
            present_slots = 0
            absent_slots = 0
            for membership in scope.player_memberships:
                code = classify_scope(scope, session, membership.user_id)
                if code == "present":
                    present_slots += 1
                elif code == "absent":
                    absent_slots += 1
            denom = present_slots + absent_slots
            trend.append(
                {
                    "period_key": f"session-{session.id}",
                    "period_start": session.scheduled_date.isoformat(),
                    "period_end": session.scheduled_date.isoformat(),
                    "label": session.scheduled_date.isoformat(),
                    "session_id": session.id,
                    "session_title": session.title,
                    "closed_sessions": 1,
                    "present_slots": present_slots,
                    "absent_slots": absent_slots,
                    "attendance_rate_percent": (round(100.0 * present_slots / denom, 2) if denom else None),
                }
            )
    else:
        week_buckets: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: {"present": 0, "absent": 0, "sessions": 0})
        for session in scope.closed_sessions:
            iso = session.scheduled_date.isocalendar()
            key = (iso[0], iso[1])
            week_buckets[key]["sessions"] += 1
            for membership in scope.player_memberships:
                code = classify_scope(scope, session, membership.user_id)
                if code == "present":
                    week_buckets[key]["present"] += 1
                elif code == "absent":
                    week_buckets[key]["absent"] += 1

        for (year, week) in sorted(week_buckets.keys()):
            bucket = week_buckets[(year, week)]
            monday = date.fromisocalendar(year, week, 1)
            sunday = monday + timedelta(days=6)
            denom = bucket["present"] + bucket["absent"]
            trend.append(
                {
                    "period_key": f"{year}-W{week:02d}",
                    "period_start": monday.isoformat(),
                    "period_end": sunday.isoformat(),
                    "label": f"{year} W{week:02d}",
                    "closed_sessions": bucket["sessions"],
                    "present_slots": bucket["present"],
                    "absent_slots": bucket["absent"],
                    "attendance_rate_percent": (round(100.0 * bucket["present"] / denom, 2) if denom else None),
                }
            )

    return {
        "team": serialize_team_brief(team),
        "filters": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "grouping": grouping,
            "last_n_sessions": last_n_sessions,
        },
        "calculation_summary": CALCULATION_SUMMARY_TEXT,
        "today": scope.today.isoformat(),
        "roster_player_count": len(scope.player_memberships),
        "sessions_total_non_cancelled": len([s for s in scope.sessions if s.status != TrainingSession.Status.CANCELLED]),
        "closed_sessions_in_scope": len(scope.closed_sessions),
        "team_average_attendance_rate_percent": (None if team_avg is None else round(team_avg, 2)),
        "players": players_out,
        "trend": trend,
    }


def build_team_compact_summary(
    team: Team,
    *,
    start_date: date,
    end_date: date,
    last_n_sessions: Optional[int] = None,
) -> dict[str, Any]:
    """Roll-up for GET …/attendance/summary/ without per-player rows or trend."""
    scope = prepare_team_attendance_scope(
        team,
        start_date=start_date,
        end_date=end_date,
        last_n_sessions=last_n_sessions,
    )
    attended, closed = team_closed_player_slot_totals(scope)
    team_avg = (100.0 * attended / closed) if closed else None

    pending_total = upcoming_confirmed_total = 0
    for membership in scope.player_memberships:
        row = build_player_row(scope, membership)
        pending_total += row["pending_sessions"]
        upcoming_confirmed_total += row["upcoming_confirmed_sessions"]

    return {
        "team": serialize_team_brief(team),
        "filters": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "last_n_sessions": last_n_sessions,
        },
        "calculation_summary": CALCULATION_SUMMARY_TEXT,
        "today": scope.today.isoformat(),
        "roster_player_count": len(scope.player_memberships),
        "sessions_total_non_cancelled": len([s for s in scope.sessions if s.status != TrainingSession.Status.CANCELLED]),
        "closed_sessions_in_scope": len(scope.closed_sessions),
        "closed_roster_slots_present": attended,
        "closed_roster_slots_absent": closed - attended,
        "closed_roster_slots_total": closed,
        "open_roster_slots_pending": pending_total,
        "open_roster_slots_upcoming_confirmed": upcoming_confirmed_total,
        "team_average_attendance_rate_percent": (None if team_avg is None else round(team_avg, 2)),
    }


def build_player_team_summary(
    team: Team,
    player_id: int,
    *,
    start_date: date,
    end_date: date,
    last_n_sessions: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """Per-player summary for a single team roster; None if player is not an active player on the team."""
    scope = prepare_team_attendance_scope(
        team,
        start_date=start_date,
        end_date=end_date,
        last_n_sessions=last_n_sessions,
    )
    membership = next((m for m in scope.player_memberships if m.user_id == player_id), None)
    if membership is None:
        return None
    row = build_player_row(scope, membership)
    row.pop("_total_attended_slots", None)
    row.pop("_total_closed_slots", None)
    return {
        "team": serialize_team_brief(team),
        "filters": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "last_n_sessions": last_n_sessions,
        },
        "calculation_summary": CALCULATION_SUMMARY_TEXT,
        "today": scope.today.isoformat(),
        "player": row,
    }


def club_weighted_average_attendance_percent(
    club: Club,
    *,
    start_date: date,
    end_date: date,
) -> Optional[float]:
    """Weighted average across all teams in the club (each closed player-slot counts equally)."""
    teams = Team.objects.filter(club=club).select_related("club")
    num = 0
    den = 0
    for team in teams:
        scope = prepare_team_attendance_scope(team, start_date=start_date, end_date=end_date, last_n_sessions=None)
        attended, closed = team_closed_player_slot_totals(scope)
        num += attended
        den += closed
    if den == 0:
        return None
    return round(100.0 * num / den, 2)


def club_team_attendance_snapshot(
    club: Club,
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Per-team closed-slot rate for director dashboards."""
    out = []
    for team in Team.objects.filter(club=club).select_related("club").order_by("name", "id"):
        scope = prepare_team_attendance_scope(team, start_date=start_date, end_date=end_date, last_n_sessions=None)
        attended, closed = team_closed_player_slot_totals(scope)
        rate = (round(100.0 * attended / closed, 2) if closed else None)
        out.append(
            {
                "team_id": team.id,
                "team_name": team.name,
                "closed_roster_slots": closed,
                "average_rate_percent": rate,
            }
        )
    return out


# --- EP-28: coach reminders for incomplete post-session attendance ---

ATTENDANCE_INCOMPLETE_RULES_TEXT = (
    "Incomplete attendance for reminders uses the active team player roster (TeamMembership, role=player) "
    "as the expected set. A player counts as covered only if a TrainingSessionConfirmation exists for "
    "(session, player). Cancelled sessions never generate reminders. Eligibility starts after the session "
    "end time on its scheduled_date, interpreted in the active Django timezone."
)


def training_session_local_end_datetime(session: TrainingSession) -> datetime:
    tz = timezone.get_current_timezone()
    combined = datetime.combine(session.scheduled_date, session.end_time)
    if timezone.is_naive(combined):
        return timezone.make_aware(combined, tz)
    return combined


def training_session_has_ended(session: TrainingSession, *, now: Optional[datetime] = None) -> bool:
    """True when local wall-clock time is at or after scheduled_date + end_time (EP-28)."""
    now = now if now is not None else timezone.now()
    return now >= training_session_local_end_datetime(session)


def roster_player_ids_for_team(team: Team) -> list[int]:
    return list(
        TeamMembership.objects.active()
        .filter(team=team, role=TeamRole.PLAYER)
        .values_list("user_id", flat=True)
    )


def missing_attendance_confirmation_count(
    roster_player_ids: list[int],
    confirmed_player_ids: set[int],
) -> int:
    return sum(1 for pid in roster_player_ids if pid not in confirmed_player_ids)


def session_attendance_incomplete_for_coach_reminder(
    session: TrainingSession,
    roster_player_ids: list[int],
    confirmed_player_ids: set[int],
) -> bool:
    """
    True when the session should surface an incomplete-attendance reminder:
    scheduled (not cancelled), non-empty roster, at least one roster player without confirmation.
    Caller should also ensure the session has already ended (see training_session_has_ended).
    """
    if session.status == TrainingSession.Status.CANCELLED:
        return False
    if not roster_player_ids:
        return False
    return missing_attendance_confirmation_count(roster_player_ids, confirmed_player_ids) > 0
