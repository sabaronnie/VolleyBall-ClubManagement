"""
Coach team dashboard payload: KPIs, chart metrics, roster stats, and feedback (DB-backed only).
"""

from __future__ import annotations

from datetime import time
from typing import Any, Optional

from django.utils import timezone

from .models import (
    Team,
    TeamCoachFeedback,
    TeamRosterPlayerStat,
    TeamSkillCategory,
    TeamSkillDashboardMetric,
    TrainingSession,
    TrainingSessionConfirmation,
)
from .models.coach_dashboard import CoachFeedbackStatus
from .attendance_summary import format_person_name

# Stable chart category order for the dashboard UI
_SKILL_ORDER: tuple[str, ...] = (
    TeamSkillCategory.ATTACK,
    TeamSkillCategory.DEFENSE,
    TeamSkillCategory.SERVE,
    TeamSkillCategory.BLOCK,
)


def _format_time_12h(t: time) -> str:
    h, m = t.hour, t.minute
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    ampm = "AM" if h < 12 else "PM"
    return f"{h12}:{m:02d} {ampm}"


def _players_confirmed_today(team: Team) -> int:
    """Distinct roster players with a confirmation on any non-cancelled session dated today."""
    today = timezone.localdate()
    session_ids = list(
        TrainingSession.objects.filter(team=team, scheduled_date=today)
        .exclude(status=TrainingSession.Status.CANCELLED)
        .values_list("id", flat=True)
    )
    if not session_ids:
        return 0
    return (
        TrainingSessionConfirmation.objects.filter(training_session_id__in=session_ids)
        .values("player_id")
        .distinct()
        .count()
    )


def _practice_time_fields(team: Team) -> tuple[Optional[str], Optional[int]]:
    """
    Next or today's practice (training) session start time display and session id.
    Prefers the earliest training session on today's date; otherwise next future training.
    """
    today = timezone.localdate()
    today_sess = (
        TrainingSession.objects.filter(
            team=team,
            scheduled_date=today,
            session_type=TrainingSession.SessionType.TRAINING,
        )
        .exclude(status=TrainingSession.Status.CANCELLED)
        .order_by("start_time", "id")
        .first()
    )
    if today_sess:
        return _format_time_12h(today_sess.start_time), today_sess.id

    next_sess = (
        TrainingSession.objects.filter(
            team=team,
            scheduled_date__gt=today,
            session_type=TrainingSession.SessionType.TRAINING,
        )
        .exclude(status=TrainingSession.Status.CANCELLED)
        .order_by("scheduled_date", "start_time", "id")
        .first()
    )
    if next_sess:
        return _format_time_12h(next_sess.start_time), next_sess.id
    return None, None


def _next_match_payload(team: Team) -> Optional[dict[str, Any]]:
    today = timezone.localdate()
    match = (
        TrainingSession.objects.filter(
            team=team,
            session_type=TrainingSession.SessionType.MATCH,
            scheduled_date__gte=today,
        )
        .exclude(status=TrainingSession.Status.CANCELLED)
        .order_by("scheduled_date", "start_time", "id")
        .first()
    )
    if match is None:
        return None
    return {
        "session_id": match.id,
        "title": match.title,
        "scheduled_date": match.scheduled_date.isoformat(),
        "weekday_label": match.scheduled_date.strftime("%A").upper(),
        "start_time": match.start_time.strftime("%H:%M"),
        "opponent": match.opponent or "",
        "match_type": match.match_type or "",
    }


def _feedback_due_count(team: Team) -> int:
    return TeamCoachFeedback.objects.filter(
        team=team,
        status=CoachFeedbackStatus.PENDING,
    ).count()


def _chart_series(team: Team) -> dict[str, Any]:
    rows = {
        m.skill_category: m
        for m in TeamSkillDashboardMetric.objects.filter(team=team).only(
            "skill_category",
            "attendance_rate",
            "average_performance",
        )
    }
    labels: list[str] = []
    attendance: list[float] = []
    performance: list[float] = []
    categories_out: list[dict[str, Any]] = []
    for key in _SKILL_ORDER:
        row = rows.get(key)
        label = dict(TeamSkillCategory.choices).get(key, key.title())
        labels.append(label)
        if row is None:
            attendance.append(0.0)
            performance.append(0.0)
            categories_out.append(
                {
                    "key": key,
                    "label": label,
                    "attendance_rate": 0.0,
                    "average_performance": 0.0,
                }
            )
        else:
            attendance.append(float(row.attendance_rate))
            performance.append(float(row.average_performance))
            categories_out.append(
                {
                    "key": key,
                    "label": label,
                    "attendance_rate": float(row.attendance_rate),
                    "average_performance": float(row.average_performance),
                }
            )
    return {
        "labels": labels,
        "attendance": attendance,
        "average_performance": performance,
        "categories": categories_out,
    }


def _trend_for_stat(stat: TeamRosterPlayerStat) -> str:
    cur = stat.serve_percentage
    prior = stat.prior_serve_percentage
    if prior is None:
        return "flat"
    if cur > prior:
        return "up"
    if cur < prior:
        return "down"
    return "flat"


def _player_stats(team: Team) -> list[dict[str, Any]]:
    stats = list(
        TeamRosterPlayerStat.objects.filter(team=team)
        .select_related("player")
        .order_by("player__first_name", "player__last_name", "player__email")
    )
    out: list[dict[str, Any]] = []
    for stat in stats:
        sp = float(stat.serve_percentage)
        out.append(
            {
                "player_id": stat.player_id,
                "player_name": format_person_name(stat.player),
                "spikes": stat.spikes,
                "blocks": stat.blocks,
                "serve_percentage": sp,
                "trend": _trend_for_stat(stat),
            }
        )
    return out


def _recent_feedback(team: Team, *, limit: int = 10) -> list[dict[str, Any]]:
    rows = list(
        TeamCoachFeedback.objects.filter(team=team)
        .select_related("player", "coach")
        .order_by("-created_at", "-id")[:limit]
    )
    return [
        {
            "id": row.id,
            "player_name": format_person_name(row.player),
            "coach_name": format_person_name(row.coach),
            "body": row.body,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


def build_coach_team_dashboard(*, team: Team) -> dict[str, Any]:
    """Full JSON payload for GET /teams/<id>/coach-dashboard/."""
    from . import views as core_views

    practice_time_display, practice_session_id = _practice_time_fields(team)
    has_skill_metrics = TeamSkillDashboardMetric.objects.filter(team=team).exists()
    return {
        "team": core_views._serialize_team_summary(team),
        "has_skill_metrics": has_skill_metrics,
        "kpis": {
            "players_today": _players_confirmed_today(team),
            "practice_time_display": practice_time_display,
            "practice_session_id": practice_session_id,
            "next_match": _next_match_payload(team),
            "feedback_due": _feedback_due_count(team),
        },
        "attendance_vs_performance": _chart_series(team),
        "player_stats": _player_stats(team),
        "recent_feedback": _recent_feedback(team),
    }
