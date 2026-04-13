"""
Aggregated director dashboard payloads (club-scoped).

Role matrix values describe coarse UI/API access for typical accounts, aligned with
`apps.core.permissions` (director/staff overrides are not enumerated here).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from .attendance_summary import club_team_attendance_snapshot, club_weighted_average_attendance_percent
from .models import Club

LOW_PARTICIPATION_THRESHOLD_PERCENT = 70.0
MIN_CLOSED_SLOTS_FOR_TEAM_ALERT = 4


def roles_permission_matrix() -> dict[str, Any]:
    return {
        "rows": [
            {
                "action": "Attendance",
                "coach": True,
                "parents": True,
                "player": True,
            },
            {
                "action": "Payments",
                "coach": False,
                "parents": True,
                "player": False,
            },
            {
                "action": "Performance",
                "coach": True,
                "parents": True,
                "player": False,
            },
        ],
    }


def build_club_director_summary(
    club: Club,
    *,
    monthly_revenue: Decimal,
    monthly_revenue_currency: str,
    trend_start: date,
    trend_end: date,
) -> dict[str, Any]:
    """
    Club summary block for the director dashboard (all derived from attendance + ledger aggregates).
    monthly_profit matches collected fees for the month; the club does not model operating expenses yet.
    """
    avg = club_weighted_average_attendance_percent(
        club,
        start_date=trend_start,
        end_date=trend_end,
    )
    teams = club_team_attendance_snapshot(
        club,
        start_date=trend_start,
        end_date=trend_end,
    )
    ranked = [
        t
        for t in teams
        if (t.get("closed_roster_slots") or 0) > 0 and t.get("average_rate_percent") is not None
    ]
    best: Optional[dict[str, Any]] = None
    low: Optional[dict[str, Any]] = None
    if ranked:
        best_row = max(ranked, key=lambda t: (t["average_rate_percent"], -t["team_id"]))
        best = {
            "team_id": best_row["team_id"],
            "team_name": best_row["team_name"],
            "rate_percent": best_row["average_rate_percent"],
        }
        worst = min(ranked, key=lambda t: (t["average_rate_percent"], t["team_id"]))
        if (
            float(worst["average_rate_percent"]) < LOW_PARTICIPATION_THRESHOLD_PERCENT
            and int(worst["closed_roster_slots"] or 0) >= MIN_CLOSED_SLOTS_FOR_TEAM_ALERT
        ):
            low = {
                "team_id": worst["team_id"],
                "team_name": worst["team_name"],
                "rate_percent": worst["average_rate_percent"],
                "message": (
                    f"{worst['team_name']} is below {LOW_PARTICIPATION_THRESHOLD_PERCENT:.0f}% attendance "
                    f"in the last 30 days ({worst['average_rate_percent']:.1f}%)."
                ),
            }

    return {
        "average_attendance_percent": avg,
        "best_participating_team": best,
        "low_participation": low,
        "monthly_profit": str(monthly_revenue),
        "monthly_profit_currency": monthly_revenue_currency,
        "monthly_profit_basis": "collected_ledger_entries_no_expenses_modeled",
    }
