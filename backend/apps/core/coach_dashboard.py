"""
Coach team dashboard payload: KPIs, chart metrics, roster stats, and feedback (DB-backed only).
"""

from __future__ import annotations

from datetime import time, timedelta
from decimal import Decimal
from typing import Any, Optional

from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from .attendance_summary import build_team_compact_summary, format_person_name, team_attendance_daily_series
from .director_dashboard import LOW_PARTICIPATION_THRESHOLD_PERCENT, MIN_CLOSED_SLOTS_FOR_TEAM_ALERT
from .models import (
    FeePaymentLedgerEntry,
    PlayerFeeRecord,
    Team,
    TeamCoachFeedback,
    TeamRosterPlayerStat,
    TeamSkillCategory,
    TeamSkillDashboardMetric,
    TrainingSession,
    TrainingSessionConfirmation,
)
from .models.coach_dashboard import CoachFeedbackStatus

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


def _team_workspace_overview(team: Team) -> dict[str, Any]:
    from .payment_views import _family_bundles_from_records

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_local = timezone.localdate()
    att_start = today_local - timedelta(days=29)
    att_end = today_local

    compact_summary = build_team_compact_summary(
        team,
        start_date=att_start,
        end_date=att_end,
    )
    monthly_revenue = (
        FeePaymentLedgerEntry.objects.filter(
            fee_record__team=team,
            recorded_at__gte=month_start,
        ).aggregate(total=Coalesce(Sum("amount"), Decimal("0.00")))["total"]
    )

    outstanding_families = (
        PlayerFeeRecord.objects.filter(team=team)
        .annotate(rem=F("amount_due") - F("amount_paid"))
        .filter(rem__gt=0)
        .values("player_id")
        .distinct()
        .count()
    )

    all_records = list(
        PlayerFeeRecord.objects.filter(team=team).select_related("player", "team").order_by("-due_date", "-id")
    )
    currency = all_records[0].currency if all_records else "USD"
    family_summaries = _family_bundles_from_records(all_records)
    outstanding_summaries = [b for b in family_summaries if Decimal(b["total_remaining"]) > 0]
    outstanding_summaries.sort(key=lambda b: (-Decimal(b["total_remaining"]), b["family_label"].lower()))
    paid_summaries = [b for b in family_summaries if Decimal(b["total_remaining"]) <= 0]
    paid_summaries.sort(key=lambda b: (b["family_label"].lower(), b["player_id"]))
    preview_families = list(outstanding_summaries[:8])
    if len(preview_families) < 8:
        preview_families.extend(paid_summaries[: 8 - len(preview_families)])

    team_attendance_rate = compact_summary["team_average_attendance_rate_percent"]
    closed_slots = int(compact_summary["closed_roster_slots_total"] or 0)
    best_team = None
    low_participation = None
    if team_attendance_rate is not None and closed_slots > 0:
        best_team = {
            "team_id": team.id,
            "team_name": team.name,
            "rate_percent": team_attendance_rate,
        }
        if (
            float(team_attendance_rate) < LOW_PARTICIPATION_THRESHOLD_PERCENT
            and closed_slots >= MIN_CLOSED_SLOTS_FOR_TEAM_ALERT
        ):
            low_participation = {
                "team_id": team.id,
                "team_name": team.name,
                "rate_percent": team_attendance_rate,
                "message": (
                    f"{team.name} is below {LOW_PARTICIPATION_THRESHOLD_PERCENT:.0f}% attendance "
                    f"in the last 30 days ({float(team_attendance_rate):.1f}%)."
                ),
            }

    payments_overview = [
        {
            "player_id": bundle["player_id"],
            "family_label": bundle["family_label"],
            "total_paid": bundle["total_paid"],
            "total_remaining": bundle["total_remaining"],
            "currency": bundle["currency"],
            "status": bundle["overall_status"],
        }
        for bundle in preview_families
    ]

    return {
        "kpis": {
            "registration_player_count": compact_summary["roster_player_count"],
            "monthly_revenue": str(monthly_revenue),
            "monthly_revenue_currency": currency,
            "attendance_rate": team_attendance_rate,
            "outstanding_payer_count": outstanding_families,
        },
        "attendance_trend_30d": {
            "calculation_summary": compact_summary["calculation_summary"],
            "filters": {
                "start_date": att_start.isoformat(),
                "end_date": att_end.isoformat(),
            },
            "points": team_attendance_daily_series(
                team,
                start_date=att_start,
                end_date=att_end,
            ),
        },
        "payments_overview": payments_overview,
        "team_summary": {
            "average_attendance_percent": team_attendance_rate,
            "best_participating_team": best_team,
            "low_participation": low_participation,
            "monthly_profit": str(monthly_revenue),
            "monthly_profit_currency": currency,
            "monthly_profit_basis": "collected_ledger_entries_no_expenses_modeled",
        },
        "family_summaries": preview_families,
    }


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
        "workspace_overview": _team_workspace_overview(team),
    }
