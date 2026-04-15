"""Director payment and fee tracking API."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage, send_mail
from django.db import transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .attendance_summary import (
    CALCULATION_SUMMARY_TEXT,
    club_attendance_daily_series,
    club_team_attendance_snapshot,
    club_weighted_average_attendance_percent,
)
from .director_dashboard import build_club_director_summary, roles_permission_matrix
from .decorators import login_required
from .models import (
    Club,
    DirectorPaymentAuditLog,
    FeePaymentLedgerEntry,
    ParentPlayerRelation,
    PaymentSchedule,
    PlayerFeeRecord,
    Team,
    TeamMembership,
    TeamRole,
)
from .permissions import can_manage_team, can_player_make_payments, can_view_team, is_club_director

logger = logging.getLogger(__name__)


def _parse_json(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _serialize_player_mini(user):
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "display_name": name or user.email,
    }


def _family_label(player):
    name = f"{player.first_name or ''} {player.last_name or ''}".strip()
    return name or player.email


def _serialize_fee_record(record: PlayerFeeRecord):
    player = record.player
    return {
        "id": record.id,
        "player": _serialize_player_mini(player),
        "family_label": _family_label(player),
        "team_id": record.team_id,
        "team_name": record.team.name if record.team else None,
        "description": record.description,
        "amount_due": str(record.amount_due),
        "amount_paid": str(record.amount_paid),
        "remaining": str(record.remaining()),
        "currency": record.currency,
        "due_date": record.due_date.isoformat(),
        "billing_period_start": record.billing_period_start.isoformat()
        if record.billing_period_start
        else None,
        "paid_at": record.paid_at.isoformat() if record.paid_at else None,
        "status": record.status(),
    }


def _family_overall_status(lines: list[PlayerFeeRecord]) -> str:
    active = [r for r in lines if r.remaining() > Decimal("0")]
    if not active:
        return "paid"
    today = timezone.localdate()
    if any(r.due_date < today for r in active):
        return "overdue"
    return "pending"


def _family_bundles_from_records(records: list[PlayerFeeRecord]) -> list[dict]:
    """One entry per player with itemized fee lines and rolled-up totals."""
    by_player: dict[int, list[PlayerFeeRecord]] = {}
    order: list[int] = []
    for rec in records:
        pid = rec.player_id
        if pid not in by_player:
            by_player[pid] = []
            order.append(pid)
        by_player[pid].append(rec)
    bundles: list[dict] = []
    for pid in order:
        lines = by_player[pid]
        player = lines[0].player
        total_rem = sum((max(r.remaining(), Decimal("0")) for r in lines), Decimal("0"))
        total_paid = sum((r.amount_paid for r in lines), Decimal("0"))
        currency = lines[0].currency
        bundles.append(
            {
                "player_id": player.id,
                "family_label": _family_label(player),
                "player": _serialize_player_mini(player),
                "total_remaining": str(total_rem),
                "total_paid": str(total_paid),
                "currency": currency,
                "overall_status": _family_overall_status(lines),
                "lines": [_serialize_fee_record(r) for r in lines],
            }
        )
    bundles.sort(key=lambda b: (b["family_label"].lower(), b["player_id"]))
    return bundles


def _outstanding_family_notice_subject_body(club: Club, player, records: list[PlayerFeeRecord]):
    subject = f"Outstanding balance: {club.name} — {_family_label(player)}"
    parts = [
        f"This notice is from {club.name}.\n\n",
        f"Player / family: {_family_label(player)}\n\n",
        "The following fee line(s) currently have a balance due:\n\n",
    ]
    for rec in records:
        parts.append(
            f"- {rec.description}\n"
            f"  Remaining: {rec.currency} {rec.remaining()} (due {rec.due_date.isoformat()})\n"
            f"  Status: {rec.status()}\n\n",
        )
    parts.append("Please arrange payment according to your club’s instructions.\n")
    return subject, "".join(parts)


def _due_today_family_bundle_subject_body(club: Club, player, records: list[PlayerFeeRecord]):
    today = timezone.localdate()
    subject = f"Fees due today: {club.name} — {_family_label(player)}"
    parts = [
        f"This notice is from {club.name}.\n\n",
        f"Player / family: {_family_label(player)}\n",
        f"Due date: {today.isoformat()}\n\n",
        "The following fee line(s) are due today:\n\n",
    ]
    for rec in records:
        parts.append(
            f"- {rec.description}\n"
            f"  Amount due: {rec.currency} {rec.amount_due}\n"
            f"  Amount paid: {rec.currency} {rec.amount_paid}\n"
            f"  Remaining: {rec.currency} {rec.remaining()}\n\n",
        )
    parts.append("Please arrange payment according to your club’s instructions.\n")
    return subject, "".join(parts)


def _club_payment_json(club: Club):
    return {
        "id": club.id,
        "name": club.name,
        "default_monthly_player_fee": str(club.default_monthly_player_fee),
    }


def _first_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _first_of_next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def ensure_monthly_fee_for_new_player(team: Team, player):
    """
    When a player joins a team, open the next calendar month's dues (due on the 1st).
    Skips if the club default fee is zero or less.
    """
    club = team.club
    amount = club.default_monthly_player_fee
    if amount <= 0:
        return None
    period = _first_of_next_month(timezone.localdate())
    desc = f"Monthly dues ({period.strftime('%B %Y')})"
    rec, _created = PlayerFeeRecord.objects.get_or_create(
        club=club,
        player=player,
        team=team,
        billing_period_start=period,
        defaults={
            "description": desc,
            "amount_due": amount,
            "amount_paid": Decimal("0.00"),
            "currency": "USD",
            "due_date": period,
        },
    )
    return rec


def materialize_monthly_fees_for_club(club: Club, period_start: date) -> int:
    """
    Ensure every active rostered player has a fee row for period_start (must be 1st of month).
    Returns count of newly created rows.
    """
    if period_start.day != 1:
        raise ValueError("period_start must be the first day of a month.")
    amount = club.default_monthly_player_fee
    if amount <= 0:
        return 0
    desc = f"Monthly dues ({period_start.strftime('%B %Y')})"
    created = 0
    memberships = (
        TeamMembership.objects.active()
        .filter(team__club=club, role=TeamRole.PLAYER)
        .select_related("team", "user")
    )
    for m in memberships:
        _, was_created = PlayerFeeRecord.objects.get_or_create(
            club=club,
            player=m.user,
            team=m.team,
            billing_period_start=period_start,
            defaults={
                "description": desc,
                "amount_due": amount,
                "amount_paid": Decimal("0.00"),
                "currency": "USD",
                "due_date": period_start,
            },
        )
        if was_created:
            created += 1
    return created


def _renewals_due_today_queryset(club: Club, on_date: date):
    return (
        PlayerFeeRecord.objects.filter(club=club, due_date=on_date)
        .annotate(rem=F("amount_due") - F("amount_paid"))
        .filter(rem__gt=0)
        .select_related("player", "team")
    )


def _new_fee_notice_subject_body(club: Club, rec: PlayerFeeRecord):
    subject = f"New club fee posted: {club.name} — {rec.description}"
    body = (
        f"{club.name} has added a new fee line to your account.\n\n"
        f"Player: {_family_label(rec.player)}\n"
        f"Description: {rec.description}\n"
        f"Amount due: {rec.currency} {rec.amount_due}\n"
        f"Amount paid: {rec.currency} {rec.amount_paid}\n"
        f"Remaining: {rec.currency} {rec.remaining()}\n"
        f"Due date: {rec.due_date.isoformat()}\n\n"
        "Please arrange payment according to your club’s instructions.\n"
    )
    return subject, body


def _reminder_subject_body(club: Club, rec: PlayerFeeRecord):
    subject = f"Payment reminder: {club.name} — {rec.description}"
    body = (
        f"This is a payment reminder from {club.name}.\n\n"
        f"Player: {_family_label(rec.player)}\n"
        f"Description: {rec.description}\n"
        f"Amount due: {rec.currency} {rec.amount_due}\n"
        f"Amount paid: {rec.currency} {rec.amount_paid}\n"
        f"Remaining: {rec.currency} {rec.remaining()}\n"
        f"Due date: {rec.due_date.isoformat()}\n\n"
        "Please arrange payment according to your club’s instructions.\n"
    )
    return subject, body


def _receipt_subject_body(club: Club, rec: PlayerFeeRecord):
    subject = f"Payment receipt: {club.name} — {rec.description}"
    body = (
        f"PAYMENT RECEIPT — {club.name}\n"
        f"{'=' * 40}\n\n"
        f"Player / account: {_family_label(rec.player)}\n"
        f"Description: {rec.description}\n"
        f"Invoice total: {rec.currency} {rec.amount_due}\n"
        f"Amount paid (cumulative): {rec.currency} {rec.amount_paid}\n"
        f"Balance remaining: {rec.currency} {rec.remaining()}\n"
        f"Due date: {rec.due_date.isoformat()}\n"
    )
    if rec.paid_at:
        body += f"Paid in full at: {rec.paid_at.isoformat()}\n"
    body += (
        f"\nLedger (most recent first):\n"
        + "\n".join(
            f"  {e.recorded_at.isoformat()}  {rec.currency} {e.amount}  {e.note or ''}".strip()
            for e in rec.ledger_entries.order_by("-recorded_at")[:20]
        )
        + "\n"
    )
    return subject, body


def _due_today_statement_subject_body(club: Club, rec: PlayerFeeRecord):
    """Email for fee lines due today: receipt if money received, otherwise a formal monthly notice."""
    if rec.amount_paid > 0:
        return _receipt_subject_body(club, rec)
    subject = f"Monthly fee due: {club.name} — {rec.description}"
    body = (
        f"This is your monthly fee notice from {club.name}.\n\n"
        f"Player: {_family_label(rec.player)}\n"
        f"Description: {rec.description}\n"
        f"Amount due: {rec.currency} {rec.amount_due}\n"
        f"Amount paid: {rec.currency} {rec.amount_paid}\n"
        f"Remaining: {rec.currency} {rec.remaining()}\n"
        f"Due date: {rec.due_date.isoformat()}\n\n"
        "Please arrange payment according to your club’s instructions.\n"
    )
    return subject, body


def _assert_director_club(user, club: Club):
    if not is_club_director(user, club):
        return JsonResponse(
            {"errors": {"authorization": "Only a director of this club can access payment data."}},
            status=403,
        )
    return None


def _player_ids_in_club(club: Club):
    return set(
        TeamMembership.objects.active()
        .filter(team__club=club, role=TeamRole.PLAYER)
        .values_list("user_id", flat=True)
        .distinct()
    )


def _payments_require_team_roster() -> bool:
    return bool(getattr(settings, "PAYMENTS_REQUIRE_TEAM_ROSTER", True))


def _assert_player_on_club_roster_for_fees(club: Club, player_id: int) -> JsonResponse | None:
    """
    When PAYMENTS_REQUIRE_TEAM_ROSTER is True, only active rostered players may be fee targets.
    When False (local testing), any existing user id is accepted for lookup / manual fee creation.
    """
    if not _payments_require_team_roster():
        return None
    if player_id not in _player_ids_in_club(club):
        return JsonResponse(
            {
                "errors": {
                    "player_id": "That user is not an active rostered player in this club.",
                },
            },
            status=400,
        )
    return None


def _recipient_emails_for_player(player):
    emails = []
    if player.email:
        emails.append(player.email.strip())
    for rel in ParentPlayerRelation.objects.approved().filter(player=player).select_related("parent"):
        if rel.parent.email:
            e = rel.parent.email.strip()
            if e and e not in emails:
                emails.append(e)
    return emails


def _send_fee_emails(subject: str, body: str, to_emails: list[str]) -> tuple[bool, str | None]:
    if not to_emails:
        return False, "No email addresses on file for this player or linked parents."
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            to_emails,
            fail_silently=False,
        )
        return True, None
    except Exception as exc:
        logger.exception("Fee-related email send failed")
        return False, str(exc)


def _send_fee_email_with_pdf(
    subject: str,
    body: str,
    to_emails: list[str],
    pdf_bytes: bytes,
    pdf_filename: str,
) -> tuple[bool, str | None]:
    if not to_emails:
        return False, "No email addresses on file for this player or linked parents."
    try:
        msg = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, to_emails)
        msg.attach(pdf_filename, pdf_bytes, "application/pdf")
        msg.send(fail_silently=False)
        return True, None
    except Exception as exc:
        logger.exception("Fee-related email with PDF failed")
        return False, str(exc)


def _reminder_pdf_bytes(club: Club, rec: PlayerFeeRecord) -> bytes:
    from .payment_pdf import build_reminder_pdf_bytes

    return build_reminder_pdf_bytes(
        club_name=club.name,
        player_name=_family_label(rec.player),
        player_email=rec.player.email or "",
        team_name=rec.team.name if rec.team else None,
        description=rec.description,
        amount_due=str(rec.amount_due),
        amount_paid=str(rec.amount_paid),
        remaining=str(rec.remaining()),
        currency=rec.currency,
        due_date=rec.due_date.isoformat(),
    )


def _receipt_pdf_bytes(club: Club, rec: PlayerFeeRecord) -> bytes:
    from .payment_pdf import build_receipt_pdf_bytes

    ledger_lines = [
        f"{e.recorded_at.isoformat()}  {rec.currency} {e.amount}  {(e.note or '').strip()}".strip()
        for e in rec.ledger_entries.order_by("-recorded_at")[:25]
    ]
    return build_receipt_pdf_bytes(
        club_name=club.name,
        player_name=_family_label(rec.player),
        player_email=rec.player.email or "",
        team_name=rec.team.name if rec.team else None,
        description=rec.description,
        amount_due=str(rec.amount_due),
        amount_paid=str(rec.amount_paid),
        remaining=str(rec.remaining()),
        currency=rec.currency,
        due_date=rec.due_date.isoformat(),
        paid_at=rec.paid_at.isoformat() if rec.paid_at else None,
        ledger_lines=ledger_lines or ["(no ledger entries)"],
    )


def _fee_line_items_for_pdf(records: list[PlayerFeeRecord]) -> tuple[list[dict], str, str]:
    items: list[dict] = []
    total = Decimal("0")
    cur = "USD"
    for r in records:
        rem = max(r.remaining(), Decimal("0"))
        total += rem
        cur = r.currency
        items.append(
            {
                "description": r.description,
                "team": r.team.name if r.team else None,
                "due_date": r.due_date.isoformat(),
                "amount_due": str(r.amount_due),
                "amount_paid": str(r.amount_paid),
                "remaining": str(r.remaining()),
                "currency": r.currency,
            }
        )
    return items, str(total), cur


def _balance_summary_pdf_bytes(
    club: Club,
    player,
    records: list[PlayerFeeRecord],
    *,
    title: str,
    as_of: date | None = None,
) -> bytes:
    from .payment_pdf import build_balance_summary_pdf_bytes

    as_of_d = as_of or timezone.localdate()
    items, total_rem, cur = _fee_line_items_for_pdf(records)
    return build_balance_summary_pdf_bytes(
        title=title,
        club_name=club.name,
        player_name=_family_label(player),
        player_email=player.email or "",
        as_of_date=as_of_d.isoformat(),
        line_items=items,
        total_remaining=total_rem,
        total_currency=cur,
        cleared_message=None,
    )


def _balance_cleared_pdf_bytes(club: Club, player, *, as_of: date | None = None) -> bytes:
    from .payment_pdf import build_balance_summary_pdf_bytes

    as_of_d = as_of or timezone.localdate()
    msg = (
        "A payment was applied to your account.\n\n"
        "You currently have no outstanding club fee lines for this club.\n\n"
        f"Statement date: {as_of_d.isoformat()}"
    )
    return build_balance_summary_pdf_bytes(
        title="Updated account balance",
        club_name=club.name,
        player_name=_family_label(player),
        player_email=player.email or "",
        as_of_date=as_of_d.isoformat(),
        line_items=[],
        total_remaining="0.00",
        total_currency="USD",
        cleared_message=msg,
    )


def _email_updated_balance_pdf_after_payment(club: Club, player, actor) -> None:
    """Email player and linked parents a PDF balance after a payment (logs failures)."""
    try:
        to_emails = _recipient_emails_for_player(player)
        if not to_emails:
            return
        all_recs = list(
            PlayerFeeRecord.objects.filter(club=club, player=player)
            .select_related("team")
            .order_by("-due_date", "-id")
        )
        outstanding = [r for r in all_recs if r.remaining() > Decimal("0")]
        subject = f"Updated balance: {club.name} — {_family_label(player)}"
        if outstanding:
            body = (
                "A payment was recorded on your account.\n\n"
                "The attached PDF lists every open fee line for this club and your current amount remaining on each, "
                "plus the total still due.\n\n"
                "Please arrange payment according to your club's instructions.\n\n"
                "A PDF summary is attached.\n"
            )
            pdf = _balance_summary_pdf_bytes(club, player, outstanding, title="Updated account balance")
        else:
            body = (
                "A payment was recorded on your account.\n\n"
                "You have no remaining balance on club fee lines for this club at this time.\n\n"
                "A confirmation PDF is attached.\n"
            )
            pdf = _balance_cleared_pdf_bytes(club, player)
        ok, err_msg = _send_fee_email_with_pdf(
            subject,
            body,
            to_emails,
            pdf,
            "club_balance_summary.pdf",
        )
        if not ok:
            logger.warning("Balance update email failed: %s", err_msg)
            return
        _log_action(
            club,
            actor,
            DirectorPaymentAuditLog.Action.REMINDER_SENT,
            f"Automatic balance PDF emailed to {', '.join(to_emails)} after payment.",
            outstanding[0] if outstanding else None,
        )
    except Exception:
        logger.exception("Unexpected error sending balance update PDF")


def _log_action(club, actor, action, detail, fee_record=None):
    DirectorPaymentAuditLog.objects.create(
        club=club,
        actor=actor,
        action=action,
        detail=detail[:4000],
        fee_record=fee_record,
    )


@login_required
@require_GET
def director_payment_overview(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    player_ids = _player_ids_in_club(club)
    registration_count = len(player_ids)

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    monthly_revenue = (
        FeePaymentLedgerEntry.objects.filter(
            fee_record__club=club,
            recorded_at__gte=month_start,
        ).aggregate(total=Coalesce(Sum("amount"), Decimal("0.00")))["total"]
    )

    outstanding_families = (
        PlayerFeeRecord.objects.filter(club=club)
        .annotate(rem=F("amount_due") - F("amount_paid"))
        .filter(rem__gt=0)
        .values("player_id")
        .distinct()
        .count()
    )

    all_records = list(
        PlayerFeeRecord.objects.filter(club=club).select_related("player", "team").order_by("-due_date", "-id")
    )
    family_summaries = _family_bundles_from_records(all_records)
    outstanding_summaries = [b for b in family_summaries if Decimal(b["total_remaining"]) > 0]
    outstanding_summaries.sort(key=lambda b: (-Decimal(b["total_remaining"]), b["family_label"].lower()))
    paid_summaries = [b for b in family_summaries if Decimal(b["total_remaining"]) <= 0]
    paid_summaries.sort(key=lambda b: (b["family_label"].lower(), b["player_id"]))
    preview_families = list(outstanding_summaries[:8])
    if len(preview_families) < 8:
        preview_families.extend(paid_summaries[: 8 - len(preview_families)])

    today_local = timezone.localdate()
    att_start = today_local - timedelta(days=29)
    att_end = today_local
    club_att_pct = club_weighted_average_attendance_percent(
        club,
        start_date=att_start,
        end_date=att_end,
    )
    attendance_trend_points = club_attendance_daily_series(
        club,
        start_date=att_start,
        end_date=att_end,
    )
    club_summary = build_club_director_summary(
        club,
        monthly_revenue=monthly_revenue,
        monthly_revenue_currency="USD",
        trend_start=att_start,
        trend_end=att_end,
    )
    payments_overview = [
        {
            "player_id": b["player_id"],
            "family_label": b["family_label"],
            "total_paid": b["total_paid"],
            "total_remaining": b["total_remaining"],
            "currency": b["currency"],
            "status": b["overall_status"],
        }
        for b in preview_families
    ]

    return JsonResponse(
        {
            "club": _club_payment_json(club),
            "kpis": {
                "registration_player_count": registration_count,
                "monthly_revenue": str(monthly_revenue),
                "monthly_revenue_currency": "USD",
                "attendance_rate": club_att_pct,
                "outstanding_payer_count": outstanding_families,
            },
            "attendance": {
                "calculation_summary": CALCULATION_SUMMARY_TEXT,
                "filters": {
                    "start_date": att_start.isoformat(),
                    "end_date": att_end.isoformat(),
                },
                "club_average_rate_percent": club_att_pct,
                "by_team": club_team_attendance_snapshot(
                    club,
                    start_date=att_start,
                    end_date=att_end,
                ),
            },
            "attendance_trend_30d": {
                "calculation_summary": CALCULATION_SUMMARY_TEXT,
                "filters": {
                    "start_date": att_start.isoformat(),
                    "end_date": att_end.isoformat(),
                },
                "points": attendance_trend_points,
            },
            "payments_overview": payments_overview,
            "roles_permission_matrix": roles_permission_matrix(),
            "club_summary": club_summary,
            "family_summaries": preview_families,
        }
    )


@login_required
@require_GET
def director_payment_rows(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    status_filter = (request.GET.get("status") or "").strip().lower()
    qs = (
        PlayerFeeRecord.objects.filter(club=club)
        .select_related("player", "team")
        .order_by("-due_date", "player__first_name", "player__last_name")
    )

    if status_filter in ("paid", "pending", "overdue"):
        qs = qs.annotate(rem=F("amount_due") - F("amount_paid"))
        if status_filter == "paid":
            qs = qs.filter(rem__lte=0)
        elif status_filter == "pending":
            qs = qs.filter(rem__gt=0, due_date__gte=timezone.localdate())
        else:
            qs = qs.filter(rem__gt=0, due_date__lt=timezone.localdate())

    records = list(qs)
    families = _family_bundles_from_records(records)

    return JsonResponse(
        {
            "club": _club_payment_json(club),
            "status_filter": status_filter or None,
            "families": families,
        }
    )


@login_required
@require_GET
def director_payment_logs(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    try:
        limit = min(int(request.GET.get("limit", "100")), 500)
    except ValueError:
        limit = 100

    logs = (
        DirectorPaymentAuditLog.objects.filter(club=club)
        .select_related("actor", "fee_record")
        .order_by("-created_at")[:limit]
    )
    out = []
    for log in logs:
        out.append(
            {
                "id": log.id,
                "action": log.action,
                "action_label": log.get_action_display(),
                "detail": log.detail,
                "created_at": log.created_at.isoformat(),
                "actor": _serialize_player_mini(log.actor),
                "fee_record_id": log.fee_record_id,
            }
        )
    return JsonResponse({"club": _club_payment_json(club), "logs": out})


@login_required
@require_GET
def director_payment_lookup_player(request, club_id):
    """Return fee lines for a player in this club (for director forms)."""
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    try:
        player_id = int(request.GET.get("player_id", ""))
    except ValueError:
        return JsonResponse({"errors": {"player_id": "Enter a numeric user id."}}, status=400)

    roster_err = _assert_player_on_club_roster_for_fees(club, player_id)
    if roster_err is not None:
        return roster_err

    player = get_user_model().objects.filter(pk=player_id).first()
    if not player:
        return JsonResponse({"errors": {"player_id": "User not found."}}, status=404)

    qs = (
        PlayerFeeRecord.objects.filter(club=club, player_id=player_id)
        .annotate(rem=F("amount_due") - F("amount_paid"))
        .filter(rem__gt=0)
        .select_related("player", "team")
        .order_by("-due_date", "-id")
    )
    rows = list(qs[:2000])
    serialized = [_serialize_fee_record(r) for r in rows]
    primary = rows[0] if rows else None
    outstanding_total = sum((max(r.remaining(), Decimal("0")) for r in rows), Decimal("0"))

    return JsonResponse(
        {
            "club": _club_payment_json(club),
            "player": _serialize_player_mini(player),
            "fee_rows": serialized,
            "primary_fee_record_id": primary.id if primary else None,
            "outstanding_line_count": len(rows),
            "outstanding_total_remaining": str(outstanding_total),
        }
    )


@login_required
@require_GET
def director_download_receipt_pdf(request, club_id, record_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    rec = get_object_or_404(
        PlayerFeeRecord.objects.prefetch_related("ledger_entries").select_related("player", "team"),
        pk=record_id,
        club=club,
    )
    if rec.amount_paid <= 0:
        return JsonResponse(
            {"errors": {"fee": "No payments recorded yet; there is no receipt PDF for this line."}},
            status=400,
        )

    pdf_bytes = _receipt_pdf_bytes(club, rec)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="receipt_fee_{rec.id}.pdf"'
    return response


@login_required
@csrf_exempt
@require_POST
def director_create_fee_record(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    payload = _parse_json(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    try:
        player_id = int(payload.get("player_id"))
    except (TypeError, ValueError):
        return JsonResponse({"errors": {"player_id": "A valid player_id is required."}}, status=400)

    roster_err = _assert_player_on_club_roster_for_fees(club, player_id)
    if roster_err is not None:
        return roster_err

    player = get_user_model().objects.filter(pk=player_id).first()
    if not player:
        return JsonResponse({"errors": {"player_id": "User not found."}}, status=404)

    team_id = payload.get("team_id")
    team = None
    if team_id is not None:
        try:
            team = Team.objects.get(pk=int(team_id), club=club)
        except (TypeError, ValueError, Team.DoesNotExist):
            return JsonResponse({"errors": {"team_id": "Invalid team for this club."}}, status=400)
        if _payments_require_team_roster() and not TeamMembership.objects.active().filter(
            team=team, user=player, role=TeamRole.PLAYER
        ).exists():
            return JsonResponse(
                {"errors": {"team_id": "Player is not on that team."}},
                status=400,
            )

    try:
        amount_due = Decimal(str(payload.get("amount_due", "")))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({"errors": {"amount_due": "Invalid amount_due."}}, status=400)
    if amount_due <= 0:
        return JsonResponse({"errors": {"amount_due": "amount_due must be positive."}}, status=400)

    due_raw = payload.get("due_date")
    if not due_raw:
        return JsonResponse({"errors": {"due_date": "due_date (YYYY-MM-DD) is required."}}, status=400)
    try:
        due_date = date.fromisoformat(str(due_raw)[:10])
    except ValueError:
        return JsonResponse({"errors": {"due_date": "Use YYYY-MM-DD for due_date."}}, status=400)

    description = (payload.get("description") or "Club fee").strip()[:255] or "Club fee"
    currency = (payload.get("currency") or "USD").strip()[:3] or "USD"
    send_notice = bool(payload.get("email_notice"))

    with transaction.atomic():
        rec = PlayerFeeRecord.objects.create(
            club=club,
            player=player,
            team=team,
            description=description,
            amount_due=amount_due,
            amount_paid=Decimal("0.00"),
            currency=currency,
            due_date=due_date,
        )
        _log_action(
            club,
            request.user,
            DirectorPaymentAuditLog.Action.FEE_CREATED,
            f"Created fee for {_family_label(player)}: {currency} {amount_due} due {due_date} — {description}",
            rec,
        )

    out = {"fee_record": _serialize_fee_record(rec)}
    if send_notice:
        rec.refresh_from_db()
        to_emails = _recipient_emails_for_player(rec.player)
        subject, body = _new_fee_notice_subject_body(club, rec)
        body += "\nA PDF summary is attached.\n"
        pdf_bytes = _reminder_pdf_bytes(club, rec)
        ok, err_msg = _send_fee_email_with_pdf(
            subject,
            body,
            to_emails,
            pdf_bytes,
            f"club_fee_notice_{rec.id}.pdf",
        )
        notice = {"attempted": True, "sent": ok, "to": to_emails}
        if not ok:
            notice["error"] = err_msg or "Could not send email."
        else:
            _log_action(
                club,
                request.user,
                DirectorPaymentAuditLog.Action.REMINDER_SENT,
                f"New fee notice (PDF) emailed to {', '.join(to_emails)} for fee #{rec.id}.",
                rec,
            )
        out["email_notice"] = notice

    return JsonResponse(out, status=201)


@login_required
@csrf_exempt
@require_POST
def director_record_fee_payment(request, club_id, record_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    rec = get_object_or_404(PlayerFeeRecord, pk=record_id, club=club)
    payload = _parse_json(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    try:
        amount = Decimal(str(payload.get("amount", "")))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({"errors": {"amount": "Invalid amount."}}, status=400)
    if amount <= 0:
        return JsonResponse({"errors": {"amount": "amount must be positive."}}, status=400)

    remaining = rec.remaining()
    if amount > remaining:
        return JsonResponse(
            {"errors": {"amount": f"Cannot exceed remaining balance ({remaining})."}},
            status=400,
        )

    note = (payload.get("note") or "").strip()[:255]

    with transaction.atomic():
        FeePaymentLedgerEntry.objects.create(fee_record=rec, amount=amount, note=note)
        rec.amount_paid = rec.amount_paid + amount
        if rec.remaining() <= 0:
            rec.paid_at = timezone.now()
        rec.save(update_fields=["amount_paid", "paid_at", "updated_at"])
        _log_action(
            club,
            request.user,
            DirectorPaymentAuditLog.Action.PAYMENT_RECORDED,
            f"Recorded {rec.currency} {amount} toward fee #{rec.id} ({_family_label(rec.player)}). {note}",
            rec,
        )

    rec.refresh_from_db()
    _email_updated_balance_pdf_after_payment(club, rec.player, request.user)
    return JsonResponse({"fee_record": _serialize_fee_record(rec)})


@login_required
@csrf_exempt
@require_POST
def director_send_payment_reminder(request, club_id, record_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    rec = get_object_or_404(PlayerFeeRecord, pk=record_id, club=club)
    if rec.remaining() <= 0:
        return JsonResponse({"errors": {"fee": "Nothing due on this fee line."}}, status=400)

    to_emails = _recipient_emails_for_player(rec.player)
    subject, body = _reminder_subject_body(club, rec)
    body += "\nA PDF copy of this notice is attached.\n"
    pdf_bytes = _reminder_pdf_bytes(club, rec)
    ok, err_msg = _send_fee_email_with_pdf(
        subject,
        body,
        to_emails,
        pdf_bytes,
        f"payment_reminder_{rec.id}.pdf",
    )
    if not ok:
        return JsonResponse({"errors": {"email": err_msg or "Could not send email."}}, status=502)

    _log_action(
        club,
        request.user,
        DirectorPaymentAuditLog.Action.REMINDER_SENT,
        f"Reminder (with PDF) sent to {', '.join(to_emails)} for fee #{rec.id} ({rec.currency} {rec.remaining()} remaining).",
        rec,
    )
    return JsonResponse({"ok": True, "sent_to": to_emails})


@login_required
@csrf_exempt
@require_POST
def director_send_receipt(request, club_id, record_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    rec = get_object_or_404(PlayerFeeRecord, pk=record_id, club=club)
    if rec.amount_paid <= 0:
        return JsonResponse({"errors": {"fee": "No payments recorded yet; nothing to receipt."}}, status=400)

    to_emails = _recipient_emails_for_player(rec.player)
    subject, body = _receipt_subject_body(club, rec)
    body += "\nA PDF receipt is attached.\n"
    pdf_bytes = _receipt_pdf_bytes(club, rec)
    ok, err_msg = _send_fee_email_with_pdf(
        subject,
        body,
        to_emails,
        pdf_bytes,
        f"payment_receipt_{rec.id}.pdf",
    )
    if not ok:
        return JsonResponse({"errors": {"email": err_msg or "Could not send email."}}, status=502)

    _log_action(
        club,
        request.user,
        DirectorPaymentAuditLog.Action.RECEIPT_SENT,
        f"Receipt (with PDF) emailed to {', '.join(to_emails)} for fee #{rec.id}.",
        rec,
    )
    return JsonResponse({"ok": True, "sent_to": to_emails})


@login_required
@require_GET
def director_renewals_due_today(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    today = timezone.localdate()
    rows = list(
        _renewals_due_today_queryset(club, today).order_by(
            "player__first_name",
            "player__last_name",
            "id",
        )
    )
    families = _family_bundles_from_records(rows)
    return JsonResponse(
        {
            "club": _club_payment_json(club),
            "as_of": today.isoformat(),
            "count": len(rows),
            "family_count": len(families),
            "families": families,
        }
    )


@login_required
@csrf_exempt
@require_POST
def director_materialize_monthly_fees(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    payload = _parse_json(request) or {}
    period_raw = payload.get("period_start")
    today = timezone.localdate()
    if period_raw:
        try:
            parsed = date.fromisoformat(str(period_raw)[:10])
        except ValueError:
            return JsonResponse(
                {"errors": {"period_start": "Use YYYY-MM-DD for period_start (any day in the target month)."}},
                status=400,
            )
        period = _first_of_month(parsed)
    else:
        period = _first_of_month(today)

    with transaction.atomic():
        created = materialize_monthly_fees_for_club(club, period)
        _log_action(
            club,
            request.user,
            DirectorPaymentAuditLog.Action.MONTHLY_FEES_MATERIALIZED,
            f"Materialized monthly fees for {period.isoformat()}: {created} new row(s).",
            None,
        )

    return JsonResponse(
        {
            "club": _club_payment_json(club),
            "period_start": period.isoformat(),
            "created_count": created,
        }
    )


@login_required
@csrf_exempt
@require_POST
def director_bulk_email_renewals_due_today(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    today = timezone.localdate()
    rows = list(
        _renewals_due_today_queryset(club, today)
        .prefetch_related("ledger_entries")
        .order_by("id")
    )

    emailed = 0
    receipt_count = 0
    notice_count = 0
    skipped: list[dict] = []

    for rec in rows:
        to_emails = _recipient_emails_for_player(rec.player)
        if not to_emails:
            skipped.append({"fee_record_id": rec.id, "reason": "no_recipient_email"})
            continue
        subject, body = _due_today_statement_subject_body(club, rec)
        body += "\nA PDF copy is attached.\n"
        if rec.amount_paid > 0:
            pdf_bytes = _receipt_pdf_bytes(club, rec)
            pdf_name = f"payment_statement_{rec.id}.pdf"
        else:
            pdf_bytes = _reminder_pdf_bytes(club, rec)
            pdf_name = f"payment_notice_{rec.id}.pdf"
        ok, err_msg = _send_fee_email_with_pdf(subject, body, to_emails, pdf_bytes, pdf_name)
        if not ok:
            skipped.append({"fee_record_id": rec.id, "reason": err_msg or "send_failed"})
            continue
        emailed += 1
        if rec.amount_paid > 0:
            receipt_count += 1
        else:
            notice_count += 1

    detail = (
        f"Due {today.isoformat()}: emailed {emailed} families "
        f"({receipt_count} receipt-style, {notice_count} unpaid notices); "
        f"skipped {len(skipped)}."
    )
    _log_action(
        club,
        request.user,
        DirectorPaymentAuditLog.Action.BULK_STATEMENTS_SENT,
        detail[:4000],
        None,
    )

    return JsonResponse(
        {
            "club": _club_payment_json(club),
            "as_of": today.isoformat(),
            "emailed_count": emailed,
            "receipt_style_count": receipt_count,
            "monthly_notice_count": notice_count,
            "skipped": skipped,
        }
    )


@login_required
@csrf_exempt
@require_POST
def director_email_outstanding_notice_for_player(request, club_id):
    """Send one text notice listing all outstanding fee lines for a player in this club."""
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    payload = _parse_json(request) or {}
    try:
        player_id = int(payload.get("player_id"))
    except (TypeError, ValueError):
        return JsonResponse({"errors": {"player_id": "Provide a numeric player_id in the JSON body."}}, status=400)

    roster_err = _assert_player_on_club_roster_for_fees(club, player_id)
    if roster_err is not None:
        return roster_err

    player = get_user_model().objects.filter(pk=player_id).first()
    if not player:
        return JsonResponse({"errors": {"player_id": "User not found."}}, status=404)

    rows = list(
        PlayerFeeRecord.objects.filter(club=club, player_id=player_id)
        .annotate(rem=F("amount_due") - F("amount_paid"))
        .filter(rem__gt=0)
        .select_related("player", "team")
        .order_by("-due_date", "-id")
    )
    if not rows:
        return JsonResponse(
            {
                "club": _club_payment_json(club),
                "emailed_count": 0,
                "fee_line_count": 0,
                "skipped": [{"reason": "no_outstanding_balance"}],
            }
        )

    to_emails = _recipient_emails_for_player(player)
    if not to_emails:
        return JsonResponse(
            {"errors": {"email": "No email addresses on file for this player or linked parents."}},
            status=400,
        )

    subject, body = _outstanding_family_notice_subject_body(club, player, rows)
    body += "\nA PDF summary of these lines is attached.\n"
    pdf_bytes = _balance_summary_pdf_bytes(club, player, rows, title="Outstanding balance")
    ok, err_msg = _send_fee_email_with_pdf(
        subject,
        body,
        to_emails,
        pdf_bytes,
        "outstanding_balance_notice.pdf",
    )
    if not ok:
        return JsonResponse({"errors": {"email": err_msg or "Could not send email."}}, status=502)

    _log_action(
        club,
        request.user,
        DirectorPaymentAuditLog.Action.REMINDER_SENT,
        f"Outstanding balance notice (PDF): {len(rows)} fee line(s) emailed to {', '.join(to_emails)} for player #{player_id}.",
        rows[0],
    )

    return JsonResponse(
        {
            "club": _club_payment_json(club),
            "emailed_count": 1,
            "fee_line_count": len(rows),
            "sent_to": to_emails,
        }
    )


@login_required
@csrf_exempt
@require_POST
def director_email_renewals_due_today_for_player(request, club_id):
    """Send one combined due-today notice for all fee lines due today for a single player/family."""
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    payload = _parse_json(request) or {}
    try:
        player_id = int(payload.get("player_id"))
    except (TypeError, ValueError):
        return JsonResponse({"errors": {"player_id": "Provide a numeric player_id in the JSON body."}}, status=400)

    roster_err = _assert_player_on_club_roster_for_fees(club, player_id)
    if roster_err is not None:
        return roster_err

    player = get_user_model().objects.filter(pk=player_id).first()
    if not player:
        return JsonResponse({"errors": {"player_id": "User not found."}}, status=404)

    today = timezone.localdate()
    rows = list(
        _renewals_due_today_queryset(club, today)
        .filter(player_id=player_id)
        .prefetch_related("ledger_entries")
        .order_by("id")
    )
    if not rows:
        return JsonResponse(
            {
                "club": _club_payment_json(club),
                "as_of": today.isoformat(),
                "emailed_count": 0,
                "fee_line_count": 0,
                "skipped": [{"reason": "no_due_lines_today"}],
            }
        )

    to_emails = _recipient_emails_for_player(player)
    if not to_emails:
        return JsonResponse(
            {"errors": {"email": "No email addresses on file for this player or linked parents."}},
            status=400,
        )

    subject, body = _due_today_family_bundle_subject_body(club, player, rows)
    body += "\nA PDF summary of these lines is attached.\n"
    pdf_bytes = _balance_summary_pdf_bytes(club, player, rows, title="Fees due today")
    ok, err_msg = _send_fee_email_with_pdf(
        subject,
        body,
        to_emails,
        pdf_bytes,
        "fees_due_today_summary.pdf",
    )
    if not ok:
        return JsonResponse({"errors": {"email": err_msg or "Could not send email."}}, status=502)

    _log_action(
        club,
        request.user,
        DirectorPaymentAuditLog.Action.REMINDER_SENT,
        f"Due {today.isoformat()}: emailed {len(rows)} fee line(s) with PDF to {', '.join(to_emails)} for player #{player_id}.",
        rows[0],
    )

    return JsonResponse(
        {
            "club": _club_payment_json(club),
            "as_of": today.isoformat(),
            "emailed_count": 1,
            "fee_line_count": len(rows),
            "sent_to": to_emails,
        }
    )


# ---------------------------------------------------------------------------
# Coach: view payment status of all players on a team they manage
# ---------------------------------------------------------------------------

@login_required
@require_GET
def team_player_payments(request, team_id):
    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    if not can_manage_team(request.user, team):
        return JsonResponse(
            {"errors": {"authorization": "You must be a coach or director of this team."}},
            status=403,
        )

    player_ids = list(
        TeamMembership.objects.active()
        .filter(team=team, role=TeamRole.PLAYER)
        .values_list("user_id", flat=True)
    )

    records = (
        PlayerFeeRecord.objects.filter(team=team, player_id__in=player_ids)
        .select_related("player", "team")
        .order_by("player__last_name", "player__first_name", "-due_date", "-id")
    )

    rows = [_serialize_fee_record(rec) for rec in records]

    return JsonResponse({"team_id": team.id, "team_name": team.name, "fee_rows": rows})


# ---------------------------------------------------------------------------
# Player / parent: view own fees and record a self-service payment
# ---------------------------------------------------------------------------

@login_required
@require_GET
def my_fees(request):
    """Return the logged-in user's fee records, plus children's records for parents."""
    user = request.user
    own_records = list(
        PlayerFeeRecord.objects.filter(player=user)
        .select_related("player", "team")
        .order_by("-due_date", "-id")
    )

    children_records = []
    child_rels = ParentPlayerRelation.objects.approved().filter(parent=user).select_related("player")
    for rel in child_rels:
        recs = (
            PlayerFeeRecord.objects.filter(player=rel.player)
            .select_related("player", "team")
            .order_by("-due_date", "-id")
        )
        for r in recs:
            children_records.append(r)

    return JsonResponse(
        {
            "own_fees": [_serialize_fee_record(r) for r in own_records],
            "children_fees": [_serialize_fee_record(r) for r in children_records],
            "can_make_own_payments": can_player_make_payments(user),
        }
    )


@csrf_exempt
@login_required
@require_POST
def record_self_payment(request, record_id):
    """Player or parent records a payment (in-person or online note)."""
    payload = _parse_json(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    rec = get_object_or_404(
        PlayerFeeRecord.objects.select_related("player", "club", "team"),
        pk=record_id,
    )

    is_own = request.user.id == rec.player_id
    is_parent = ParentPlayerRelation.objects.approved().filter(
        parent=request.user, player=rec.player
    ).exists()

    if not is_own and not is_parent:
        return JsonResponse(
            {"errors": {"authorization": "You can only pay your own fees or your child's fees."}},
            status=403,
        )
    if is_own and not can_player_make_payments(request.user):
        return JsonResponse(
            {
                "errors": {
                    "authorization": (
                        "Your parent-managed settings do not allow you to make payments."
                    )
                }
            },
            status=403,
        )

    raw_amount = payload.get("amount")
    method = (payload.get("method") or "in_person").strip()
    note_text = (payload.get("note") or "").strip()

    try:
        amount = Decimal(str(raw_amount))
    except (TypeError, ValueError, InvalidOperation):
        return JsonResponse({"errors": {"amount": "Provide a valid payment amount."}}, status=400)

    remaining = rec.remaining()
    if amount <= 0 or amount > remaining:
        return JsonResponse(
            {"errors": {"amount": f"Amount must be between 0.01 and {remaining}."}},
            status=400,
        )

    with transaction.atomic():
        rec.amount_paid = rec.amount_paid + amount
        if rec.remaining() <= 0:
            rec.paid_at = timezone.now()
        rec.save(update_fields=["amount_paid", "paid_at", "updated_at"])

        ledger_note = f"Self-service payment ({method})"
        if note_text:
            ledger_note += f": {note_text}"
        FeePaymentLedgerEntry.objects.create(
            fee_record=rec,
            amount=amount,
            note=ledger_note[:255],
        )

    rec.refresh_from_db()
    _email_updated_balance_pdf_after_payment(rec.club, rec.player, request.user)
    return JsonResponse(
        {"message": "Payment recorded.", "fee": _serialize_fee_record(rec)},
        status=200,
    )


# ---------------------------------------------------------------------------
# Payment schedules — director CRUD + materialization
# ---------------------------------------------------------------------------

def _serialize_payment_schedule(sched: PaymentSchedule):
    return {
        "id": sched.id,
        "club_id": sched.club_id,
        "team_id": sched.team_id,
        "team_name": sched.team.name if sched.team else None,
        "player_id": sched.player_id,
        "player_name": (
            f"{sched.player.first_name or ''} {sched.player.last_name or ''}".strip()
            or (sched.player.email if sched.player else None)
        ) if sched.player else None,
        "scope": sched.scope,
        "frequency": sched.frequency,
        "amount": str(sched.amount),
        "currency": sched.currency,
        "description": sched.description,
        "start_date": sched.start_date.isoformat(),
        "is_active": sched.is_active,
        "created_at": sched.created_at.isoformat() if sched.created_at else None,
    }


def _target_players_for_schedule(sched: PaymentSchedule):
    """Return a list of (player, team) tuples for the schedule's scope."""
    if not sched.is_active:
        return []
    targets = []
    if sched.scope == PaymentSchedule.Scope.PLAYER:
        if sched.player:
            team = sched.team
            if not team:
                m = (
                    TeamMembership.objects.active()
                    .filter(user=sched.player, team__club=sched.club, role=TeamRole.PLAYER)
                    .select_related("team")
                    .first()
                )
                team = m.team if m else None
            targets.append((sched.player, team))
    elif sched.scope == PaymentSchedule.Scope.TEAM:
        if sched.team:
            for m in (
                TeamMembership.objects.active()
                .filter(team=sched.team, role=TeamRole.PLAYER)
                .select_related("user")
            ):
                targets.append((m.user, sched.team))
    elif sched.scope == PaymentSchedule.Scope.CLUB:
        for m in (
            TeamMembership.objects.active()
            .filter(team__club=sched.club, role=TeamRole.PLAYER)
            .select_related("user", "team")
        ):
            targets.append((m.user, m.team))
    return targets


def _materialize_schedule(sched: PaymentSchedule, due_date: date) -> int:
    """Create PlayerFeeRecord rows for every target that doesn't already have one for this due_date,
    then send notification emails to each affected player and their parents."""
    if not sched.is_active:
        return 0
    targets = _target_players_for_schedule(sched)
    created = 0
    new_records: list[PlayerFeeRecord] = []
    for player, team in targets:
        occ_key = f"sched{sched.pk}-p{player.pk}-d{due_date.isoformat()}"
        rec, was_created = PlayerFeeRecord.objects.get_or_create(
            club=sched.club,
            player=player,
            team=team,
            schedule=sched,
            due_date=due_date,
            defaults={
                "description": sched.description,
                "amount_due": sched.amount,
                "currency": sched.currency,
                # Leave null so this row does not collide with monthly dues unique
                # (club, player, team, billing_period_start).
                "billing_period_start": None,
                "schedule_occurrence_key": occ_key,
            },
        )
        if was_created:
            created += 1
            new_records.append(rec)

    for rec in new_records:
        to_emails = _recipient_emails_for_player(rec.player)
        if to_emails:
            subject, body = _new_fee_notice_subject_body(sched.club, rec)
            _send_fee_emails(subject, body, to_emails)

    return created


@csrf_exempt
@login_required
@require_POST
def create_payment_schedule(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    payload = _parse_json(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    frequency = (payload.get("frequency") or "").strip()
    scope = (payload.get("scope") or "").strip()
    description = (payload.get("description") or "").strip()
    start_date_raw = (payload.get("start_date") or "").strip()
    team_id = payload.get("team_id")
    player_id = payload.get("player_id")

    errors = {}
    if frequency not in PaymentSchedule.Frequency.values:
        errors["frequency"] = f"Must be one of: {', '.join(PaymentSchedule.Frequency.values)}."
    if scope not in PaymentSchedule.Scope.values:
        errors["scope"] = f"Must be one of: {', '.join(PaymentSchedule.Scope.values)}."
    if not description:
        errors["description"] = "Description is required."

    try:
        amount = Decimal(str(payload.get("amount", "")))
        if amount <= 0:
            errors["amount"] = "Amount must be greater than zero."
    except (TypeError, ValueError, InvalidOperation):
        errors["amount"] = "Provide a valid amount."
        amount = None

    try:
        start_dt = date.fromisoformat(start_date_raw) if start_date_raw else None
        if not start_dt:
            errors["start_date"] = "Start date is required (YYYY-MM-DD)."
    except ValueError:
        errors["start_date"] = "Invalid date format, use YYYY-MM-DD."
        start_dt = None

    team = None
    player = None
    if scope == "team":
        if not team_id:
            errors["team_id"] = "team_id is required for team scope."
        else:
            team = Team.objects.filter(pk=team_id, club=club).first()
            if not team:
                errors["team_id"] = "Team not found in this club."
    elif scope == "player":
        if not player_id:
            errors["player_id"] = "player_id is required for player scope."
        else:
            User = get_user_model()
            player = User.objects.filter(pk=player_id).first()
            if not player:
                errors["player_id"] = "Player not found."
        if team_id:
            team = Team.objects.filter(pk=team_id, club=club).first()

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    sched = PaymentSchedule.objects.create(
        club=club,
        team=team,
        player=player,
        scope=scope,
        frequency=frequency,
        amount=amount,
        currency=(payload.get("currency") or "USD").strip()[:3],
        description=description,
        start_date=start_dt,
        created_by=request.user,
    )

    created_count = _materialize_schedule(sched, start_dt)

    return JsonResponse(
        {
            "message": f"Payment schedule created. {created_count} fee record(s) generated.",
            "schedule": _serialize_payment_schedule(sched),
            "records_created": created_count,
        },
        status=201,
    )


@login_required
@require_GET
def list_payment_schedules(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err

    schedules = (
        PaymentSchedule.objects.filter(club=club)
        .select_related("team", "player")
        .order_by("-is_active", "-created_at")
    )
    return JsonResponse(
        {"schedules": [_serialize_payment_schedule(s) for s in schedules]}
    )


@csrf_exempt
@login_required
@require_POST
def deactivate_payment_schedule(request, club_id, schedule_id):
    """Soft-deactivate a payment schedule so it no longer materializes new fee rows."""
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err
    sched = get_object_or_404(PaymentSchedule.objects.select_related("team", "player"), pk=schedule_id, club=club)
    if not sched.is_active:
        return JsonResponse(
            {"message": "Schedule is already inactive.", "schedule": _serialize_payment_schedule(sched)},
            status=200,
        )
    sched.is_active = False
    sched.save(update_fields=["is_active"])
    return JsonResponse(
        {"message": "Payment schedule deactivated.", "schedule": _serialize_payment_schedule(sched)},
        status=200,
    )


@csrf_exempt
@login_required
@require_POST
def delete_payment_schedule(request, club_id, schedule_id):
    """Hard-delete an inactive schedule for this club."""
    club = get_object_or_404(Club, pk=club_id)
    err = _assert_director_club(request.user, club)
    if err:
        return err
    sched = get_object_or_404(PaymentSchedule.objects.select_related("team", "player"), pk=schedule_id, club=club)
    if sched.is_active:
        return JsonResponse(
            {"errors": {"schedule": "Deactivate the schedule before you can delete it."}},
            status=400,
        )
    sched.delete()
    return JsonResponse({"message": "Schedule removed."}, status=200)


@login_required
@require_GET
def player_team_payments(request, team_id):
    """Player or parent views their payment records for a specific team."""
    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    if not can_view_team(request.user, team):
        return JsonResponse(
            {"errors": {"authorization": "You do not have access to this team."}},
            status=403,
        )

    user = request.user
    player_ids = {user.id}
    for rel in ParentPlayerRelation.objects.approved().filter(parent=user).select_related("player"):
        player_ids.add(rel.player_id)

    records = (
        PlayerFeeRecord.objects.filter(team=team, player_id__in=player_ids)
        .select_related("player", "team")
        .order_by("-due_date", "-id")
    )

    return JsonResponse(
        {
            "team_id": team.id,
            "team_name": team.name,
            "fee_rows": [_serialize_fee_record(r) for r in records],
        }
    )
