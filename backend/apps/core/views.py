import json
import logging
import secrets
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.signing import BadSignature, SignatureExpired
from django.core.validators import EmailValidator
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST, require_http_methods

from .attendance_reminders import (
    coach_attendance_action_path,
    sync_incomplete_attendance_notifications_for_session_id,
)
from .attendance_summary import (
    CALCULATION_SUMMARY_TEXT,
    attendance_status,
    build_player_team_summary,
    build_team_attendance_analytics,
    build_team_compact_summary,
    session_roster_summary,
    training_session_has_ended,
)
from .decorators import login_required
from .payment_views import ensure_monthly_fee_for_new_player
from .models import (
    AssignedAccountRole,
    Club,
    ClubMembership,
    ClubRole,
    ContactSubmission,
    Notification,
    ParentLinkApprovalStatus,
    ParentPlayerRelation,
    PasswordResetOTP,
    RegistrationOTP,
    PlayerAccessPolicy,
    PlayerFeeRecord,
    PlayerProfile,
    Team,
    TeamInvitation,
    TeamInvitationStatus,
    TeamMembership,
    TeamRole,
    TeamScheduleEntry,
    TrainingSession,
    TrainingSessionConfirmation,
    VerificationStatus,
)
from .permissions import (
    can_add_parent_association,
    can_add_team_member,
    coach_may_add_user_to_team_roster,
    can_manage_club,
    can_manage_player,
    can_manage_team,
    can_manage_team_member,
    can_player_confirm_attendance,
    can_player_update_own_emergency_contact,
    can_parent_manage_player_access,
    can_remove_parent_association,
    can_view_team,
    is_any_club_director,
    is_parent_of_player_on_team,
    is_staff_user,
    is_team_player,
    is_user_adult,
)
from .tokens import generate_auth_token, verify_auth_token


logger = logging.getLogger(__name__)

User = get_user_model()


def _password_reset_email_configured():
    return bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)


def _contact_form_notification_recipients():
    raw = (getattr(settings, "CONTACT_NOTIFICATION_EMAIL", None) or "").strip()
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def _send_contact_submission_notification(row):
    """Email club staff when SMTP is configured; failures are logged only (row is already saved)."""
    recipients = _contact_form_notification_recipients()
    if not recipients:
        logger.warning("Contact form submission %s saved but CONTACT_NOTIFICATION_EMAIL is empty.", row.pk)
        return
    if not _password_reset_email_configured():
        logger.warning(
            "Contact form submission %s saved but outbound email is not configured (EMAIL_HOST_USER / EMAIL_HOST_PASSWORD).",
            row.pk,
        )
        return

    subject = f"[NetUp] Contact form: {row.name}"
    body = (
        "A new message was submitted via the Contact Us form.\n\n"
        f"Submission ID: {row.pk}\n"
        f"Name: {row.name}\n"
        f"Email: {row.email}\n"
        f"Role: {row.get_role_display()}\n"
        f"Phone: {row.phone or '—'}\n\n"
        f"Message:\n{row.message}\n"
    )
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send contact form notification email for submission %s", row.pk)


def _dispatch_contact_submission_notification(row):
    """Return the API response immediately; send email outside the request path when possible."""
    if settings.EMAIL_BACKEND == "django.core.mail.backends.locmem.EmailBackend":
        _send_contact_submission_notification(row)
        return

    threading.Thread(
        target=_send_contact_submission_notification,
        args=(row,),
        daemon=True,
    ).start()


def _registration_otp_minutes():
    return int(getattr(settings, "REGISTRATION_OTP_MINUTES", settings.PASSWORD_RESET_OTP_MINUTES))


def _generate_numeric_otp():
    return f"{secrets.randbelow(10**6):06d}"


def _send_password_reset_otp_email(user, otp_plain):
    minutes = settings.PASSWORD_RESET_OTP_MINUTES
    subject = "Your password reset code"
    body = (
        f"Hello,\n\n"
        f"Your password reset verification code is: {otp_plain}\n\n"
        f"This code expires in {minutes} minute(s).\n\n"
        f"If you did not request this, you can ignore this email.\n"
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def _send_registration_otp_email(email, otp_plain, first_name=""):
    minutes = _registration_otp_minutes()
    subject = "Your signup verification code"
    body = (
        f"Hello {first_name or 'there'},\n\n"
        f"Your NetUp signup verification code is: {otp_plain}\n\n"
        f"This code expires in {minutes} minute(s).\n\n"
        f"If you did not request this, you can ignore this email.\n"
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )


def _parse_json_request(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _serialize_club(club):
    return {
        "id": club.id,
        "name": club.name,
        "short_name": club.short_name,
        "description": club.description,
        "contact_email": club.contact_email,
        "contact_phone": club.contact_phone,
        "website": club.website,
        "country": club.country,
        "city": club.city,
        "address": club.address,
        "founded_year": club.founded_year,
    }


def _serialize_team(team):
    return {
        "id": team.id,
        "club_id": team.club_id,
        "club_name": team.club.name,
        "club_short_name": team.club.short_name,
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


def _serialize_team_summary(team):
    memberships = (
        TeamMembership.objects.active()
        .filter(team=team)
        .select_related("user")
        .order_by("role", "user__first_name", "user__last_name", "user__email")
    )
    coaches = [membership for membership in memberships if membership.role == TeamRole.COACH]
    players = [membership for membership in memberships if membership.role == TeamRole.PLAYER]
    captains = [membership for membership in players if membership.is_captain]

    return {
        **_serialize_team(team),
        "coach_names": [
            f"{membership.user.first_name} {membership.user.last_name}".strip()
            or membership.user.email
            for membership in coaches
        ],
        "primary_coach_name": (
            f"{coaches[0].user.first_name} {coaches[0].user.last_name}".strip()
            or coaches[0].user.email
            if coaches
            else None
        ),
        "player_count": len(players),
        "coach_count": len(coaches),
        "captain_names": [
            f"{membership.user.first_name} {membership.user.last_name}".strip()
            or membership.user.email
            for membership in captains
        ],
        "captain_count": len(captains),
    }


def _serialize_schedule_entry(entry, week_start):
    scheduled_date = week_start + timedelta(days=entry.weekday)
    return {
        "id": entry.id,
        "activity_name": entry.activity_name,
        "weekday": entry.weekday,
        "weekday_label": entry.get_weekday_display(),
        "date": scheduled_date.isoformat(),
        "start_time": entry.start_time.strftime("%H:%M"),
        "end_time": entry.end_time.strftime("%H:%M"),
        "location": entry.location,
    }


def _get_user_age(user):
    if not user.date_of_birth:
        return None

    today = timezone.localdate()
    years = today.year - user.date_of_birth.year
    if (today.month, today.day) < (user.date_of_birth.month, user.date_of_birth.day):
        years -= 1
    return years


def _can_player_self_confirm_training(player_user):
    """Adult-capable players (14+) with the Player account role may self-confirm (EP-24)."""
    if _canonical_app_role(player_user) != AssignedAccountRole.PLAYER:
        return False

    age = _get_user_age(player_user)
    if age is None:
        return False

    return age >= 14 and can_player_confirm_attendance(player_user)


def _can_parent_confirm_training(parent_user, player_user, team):
    age = _get_user_age(player_user)
    if age is None:
        return False

    return age < 14 and is_parent_of_player_on_team(parent_user, player_user, team)


def _format_person_name(user):
    return f"{user.first_name} {user.last_name}".strip() or user.email


def _serialize_training_session(session, viewer, team, player_memberships):
    confirmations_by_player_id = {
        confirmation.player_id: confirmation
        for confirmation in session.confirmations.select_related("confirmed_by", "player")
    }
    viewer_can_manage = can_manage_team(viewer, team)

    player_confirmations = []
    for membership in player_memberships:
        player = membership.user
        confirmation = confirmations_by_player_id.get(player.id)

        player_confirmations.append(
            {
                "player_id": player.id,
                "player_name": _format_person_name(player),
                "is_confirmed": confirmation is not None,
                "confirmed_at": (
                    confirmation.confirmed_at.isoformat() if confirmation else None
                ),
                "confirmed_by_name": (
                    _format_person_name(confirmation.confirmed_by)
                    if confirmation and confirmation.confirmed_by
                    else None
                ),
                "can_confirm": (
                    viewer == player and _can_player_self_confirm_training(player)
                )
                or _can_parent_confirm_training(viewer, player, team),
            }
        )

    confirmed_count = len([confirmation for confirmation in player_confirmations if confirmation["is_confirmed"]])
    pending_count = max(len(player_confirmations) - confirmed_count, 0)

    return {
        "id": session.id,
        "title": session.title,
        "session_type": session.session_type,
        "session_type_label": session.get_session_type_display(),
        "scheduled_date": session.scheduled_date.isoformat(),
        "start_time": session.start_time.strftime("%H:%M"),
        "end_time": session.end_time.strftime("%H:%M"),
        "location": session.location,
        "opponent": session.opponent,
        "match_type": session.match_type,
        "match_type_label": session.get_match_type_display() if session.match_type else "",
        "notes": session.notes,
        "notify_players": session.notify_players,
        "notify_parents": session.notify_parents,
        "status": session.status,
        "status_label": session.get_status_display(),
        "can_edit": viewer_can_manage,
        "can_cancel": viewer_can_manage and session.status != TrainingSession.Status.CANCELLED,
        "confirmed_count": confirmed_count,
        "pending_count": pending_count,
        "player_confirmations": player_confirmations,
    }


def _serialize_coach_training_session_attendance(session, team, player_memberships):
    """
    Coach/director planning view: full roster with present/pending/absent/cancelled labels,
    confirmation metadata, optional jersey/position, and summary counts (EP-25).
    """
    confirmations_by_player_id = {
        confirmation.player_id: confirmation
        for confirmation in session.confirmations.select_related("confirmed_by", "player")
    }
    user_ids = [membership.user_id for membership in player_memberships]
    profile_by_user_id = {
        profile.user_id: profile
        for profile in PlayerProfile.objects.filter(user_id__in=user_ids)
    }
    players_out = []
    for membership in player_memberships:
        player = membership.user
        confirmation = confirmations_by_player_id.get(player.id)
        is_confirmed = confirmation is not None
        status_code, status_label = attendance_status(session, is_confirmed)
        profile = profile_by_user_id.get(player.id)
        players_out.append(
            {
                "player_id": player.id,
                "player_name": _format_person_name(player),
                "attendance_status": status_code,
                "attendance_label": status_label,
                "is_confirmed": is_confirmed,
                "confirmed_at": (
                    confirmation.confirmed_at.isoformat() if confirmation else None
                ),
                "confirmed_by_name": (
                    _format_person_name(confirmation.confirmed_by)
                    if confirmation and confirmation.confirmed_by
                    else None
                ),
                "jersey_number": profile.jersey_number if profile else None,
                "primary_position": (profile.primary_position if profile else "") or "",
            }
        )

    conf_pairs = {(session.id, pid) for pid in confirmations_by_player_id}
    unconfirmed_roster_count = sum(
        1 for membership in player_memberships if membership.user_id not in confirmations_by_player_id
    )
    remind_parents_allowed = session.status != TrainingSession.Status.CANCELLED and not training_session_has_ended(
        session
    )

    return {
        "id": session.id,
        "title": session.title,
        "description": session.notes or "",
        "session_type": session.session_type,
        "session_type_label": session.get_session_type_display(),
        "scheduled_date": session.scheduled_date.isoformat(),
        "start_time": session.start_time.strftime("%H:%M"),
        "end_time": session.end_time.strftime("%H:%M"),
        "location": session.location,
        "opponent": session.opponent,
        "match_type": session.match_type,
        "match_type_label": session.get_match_type_display() if session.match_type else "",
        "notes": session.notes,
        "status": session.status,
        "status_label": session.get_status_display(),
        "team": _serialize_team(team),
        "players": players_out,
        "summary": session_roster_summary(session, player_memberships, conf_pairs),
        "unconfirmed_roster_count": unconfirmed_roster_count,
        "remind_parents_allowed": remind_parents_allowed,
    }


def _parse_training_session_payload(payload):
    if not isinstance(payload, dict):
        raise ValidationError({"body": "Invalid JSON payload."})

    title = (payload.get("title") or "").strip()
    if not title:
        raise ValidationError({"title": "Title is required."})

    session_type = (payload.get("session_type") or TrainingSession.SessionType.TRAINING).strip()
    if session_type not in TrainingSession.SessionType.values:
        raise ValidationError({"session_type": "Session type must be training or match."})

    opponent = (payload.get("opponent") or "").strip()
    match_type = (payload.get("match_type") or "").strip()

    if session_type == TrainingSession.SessionType.MATCH and not opponent:
        raise ValidationError({"opponent": "Opponent is required for match sessions."})

    if session_type == TrainingSession.SessionType.MATCH and match_type not in TrainingSession.MatchType.values:
        raise ValidationError({"match_type": "Choose a valid match type."})

    if session_type != TrainingSession.SessionType.MATCH:
        opponent = ""
        match_type = ""

    scheduled_date_value = payload.get("scheduled_date")
    try:
        scheduled_date = date.fromisoformat(scheduled_date_value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"scheduled_date": "Use YYYY-MM-DD format."}) from exc

    try:
        start_time = datetime.strptime(payload.get("start_time"), "%H:%M").time()
        end_time = datetime.strptime(payload.get("end_time"), "%H:%M").time()
    except (TypeError, ValueError) as exc:
        raise ValidationError({"time": "Start and end time must use HH:MM format."}) from exc

    if end_time <= start_time:
        raise ValidationError({"time": "End time must be after start time."})

    return {
        "title": title,
        "session_type": session_type,
        "scheduled_date": scheduled_date,
        "start_time": start_time,
        "end_time": end_time,
        "location": (payload.get("location") or "").strip(),
        "opponent": opponent,
        "match_type": match_type,
        "notes": (payload.get("notes") or "").strip(),
        "notify_players": bool(payload.get("notify_players", True)),
        "notify_parents": bool(payload.get("notify_parents", False)),
    }


def _parse_schedule_entries(payload):
    if not isinstance(payload, list):
        raise ValidationError({"entries": "Entries must be a list."})

    normalized_entries = []
    errors = []

    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            errors.append({index: "Each entry must be an object."})
            continue

        activity_name = (item.get("activity_name") or "").strip()
        if not activity_name:
            errors.append({index: {"activity_name": "Activity name is required."}})
            continue

        try:
            weekday = int(item.get("weekday"))
        except (TypeError, ValueError):
            errors.append({index: {"weekday": "Weekday must be a number from 0 to 6."}})
            continue

        if weekday not in [choice.value for choice in TeamScheduleEntry.Weekday]:
            errors.append({index: {"weekday": "Weekday must be between 0 and 6."}})
            continue

        start_time = item.get("start_time")
        end_time = item.get("end_time")

        try:
            parsed_start_time = datetime.strptime(start_time, "%H:%M").time()
            parsed_end_time = datetime.strptime(end_time, "%H:%M").time()
        except (TypeError, ValueError):
            errors.append({index: {"time": "Start and end time must use HH:MM format."}})
            continue

        if parsed_end_time <= parsed_start_time:
            errors.append({index: {"time": "End time must be after start time."}})
            continue

        normalized_entries.append(
            {
                "activity_name": activity_name,
                "weekday": weekday,
                "start_time": parsed_start_time,
                "end_time": parsed_end_time,
                "location": (item.get("location") or "").strip(),
            }
        )

    if errors:
        raise ValidationError({"entries": errors})

    return normalized_entries


def _serialize_basic_user(user):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
        "verification_status": user.verification_status,
        "role": _canonical_app_role(user) or None,
    }


def _auth_success_response(user, *, message="Authentication successful.", status=200):
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    token = generate_auth_token(user)
    return JsonResponse(
        {
            "message": message,
            "token": token,
            "user": _serialize_basic_user(user),
        },
        status=status,
    )


def _account_roles_for_user(user):
    roles = []
    if ClubMembership.objects.active().filter(user=user, role=ClubRole.CLUB_DIRECTOR).exists():
        roles.append("director")
    if TeamMembership.objects.active().filter(user=user, role=TeamRole.COACH).exists():
        roles.append("coach")
    if TeamMembership.objects.active().filter(user=user, role=TeamRole.PLAYER).exists():
        roles.append("player")
    if ParentPlayerRelation.objects.approved().filter(parent=user).exists():
        roles.append("parent")
    return roles


def _canonical_app_role(user) -> str:
    """Single primary role for admin UI derived from memberships and parent links."""
    if ClubMembership.objects.active().filter(user=user, role=ClubRole.CLUB_DIRECTOR).exists():
        return AssignedAccountRole.DIRECTOR
    if TeamMembership.objects.active().filter(user=user, role=TeamRole.COACH).exists():
        return AssignedAccountRole.COACH
    if TeamMembership.objects.active().filter(user=user, role=TeamRole.PLAYER).exists():
        return AssignedAccountRole.PLAYER
    if ParentPlayerRelation.objects.approved().filter(parent=user).exists():
        return AssignedAccountRole.PARENT
    return ""


def _display_role_for_account(request_user):
    """Single human-readable role line for profile derived from memberships and parent links."""
    membership_roles = _account_roles_for_user(request_user)
    labels = {
        "director": "Club director",
        "coach": "Coach",
        "player": "Player",
        "parent": "Parent",
    }
    order = ("director", "coach", "player", "parent")
    if membership_roles:
        ordered = [labels[r] for r in order if r in membership_roles]
        extras = [r.replace("_", " ").strip().title() for r in membership_roles if r not in labels]
        parts = ordered + extras
        return ", ".join(parts) if parts else "Member"
    return "No club role yet"


def _linked_parent_accounts(player_user):
    return [
        {
            "id": rel.parent_id,
            "email": rel.parent.email,
            "first_name": rel.parent.first_name,
            "last_name": rel.parent.last_name,
            "is_legal_guardian": rel.is_legal_guardian,
            "approval_status": rel.approval_status,
        }
        for rel in ParentPlayerRelation.objects.active()
        .filter(player=player_user)
        .select_related("parent")
    ]


def _linked_children_accounts(parent_user):
    return [
        {
            "id": rel.player_id,
            "email": rel.player.email,
            "first_name": rel.player.first_name,
            "last_name": rel.player.last_name,
            "is_legal_guardian": rel.is_legal_guardian,
            "approval_status": rel.approval_status,
        }
        for rel in ParentPlayerRelation.objects.active()
        .filter(parent=parent_user)
        .select_related("player")
    ]


def _pending_fees_summary(request_user):
    records = (
        PlayerFeeRecord.objects.filter(player=request_user)
        .select_related("club")
        .order_by("due_date", "id")
    )
    total_remaining = sum((r.remaining() for r in records if r.remaining() > 0), Decimal("0"))
    items = []
    for r in records:
        rem = r.remaining()
        if rem > 0:
            items.append(
                f"{r.club.name}: {r.description} — {r.currency} {rem} due {r.due_date.isoformat()}"
            )
    currency = records.first().currency if records.exists() else "USD"
    return {
        "currency": currency,
        "total_due": float(total_remaining),
        "items": items[:25],
        "note": "" if items else "No outstanding club fee lines on your account.",
    }


def _build_account_profile(request_user):
    return {
        "roles": _account_roles_for_user(request_user),
        "display_role": _display_role_for_account(request_user),
        "pending_fees": _pending_fees_summary(request_user),
        "linked_parents": _linked_parent_accounts(request_user),
        "linked_children": _linked_children_accounts(request_user),
    }


def _send_registration_approved_email(user):
    subject = "Your account was approved"
    body = (
        f"Hello {user.first_name or 'there'},\n\n"
        "A club director has approved your registration. You can now sign in "
        "using the email address and password you chose when you registered.\n\n"
        "If you did not create an account, you can ignore this email.\n"
    )
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception:
        logging.getLogger(__name__).exception(
            "Failed to send registration approval email to %s",
            user.email,
        )


def _send_team_membership_removed_email(*, recipient, team_name, club_name, team_id):
    if not recipient.email:
        return
    if not _password_reset_email_configured():
        return

    subject = f"Team membership removed: {team_name}"
    body = (
        f"Hello {recipient.first_name or 'there'},\n\n"
        f"The team '{team_name}' in '{club_name}' was deleted by a club director.\n"
        "Your membership for this team has been removed.\n\n"
        "If this seems unexpected, contact your club director.\n"
    )
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to send team removal email to %s for team %s",
            recipient.email,
            team_id,
        )


def _send_club_membership_removed_email(*, recipient, club_name, club_id):
    if not recipient.email:
        return
    if not _password_reset_email_configured():
        return

    subject = f"Club membership removed: {club_name}"
    body = (
        f"Hello {recipient.first_name or 'there'},\n\n"
        f"The club '{club_name}' was deleted by a club director.\n"
        "Your related club/team memberships have been removed.\n\n"
        "If this seems unexpected, contact your club administration.\n"
    )
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to send club removal email to %s for club %s",
            recipient.email,
            club_id,
        )


def _team_invitation_url(code: str) -> str:
    base = getattr(settings, "TEAM_INVITATION_URL_BASE", "http://localhost:5173/invitation")
    return f"{base.rstrip('/')}/{code}"


def _send_team_invitation_email(*, invited_email, team_name, club_name, code):
    if not invited_email:
        return
    if not _password_reset_email_configured():
        return
    invite_url = _team_invitation_url(code)
    subject = f"Invitation to join {team_name}"
    body = (
        "Hello,\n\n"
        f"You were invited to join the team '{team_name}' in '{club_name}'.\n"
        "Use the invitation link below to accept or decline:\n"
        f"{invite_url}\n\n"
        "If you do not have an account, register first with this same email, then open the same invitation link.\n"
    )
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [invited_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send team invitation email to %s", invited_email)


def _serialize_team_invitation(invite):
    return {
        "id": invite.id,
        "code": invite.code,
        "status": invite.status,
        "invited_email": invite.invited_email,
        "role": invite.role,
        "created_at": invite.created_at.isoformat() if invite.created_at else None,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "responded_at": invite.responded_at.isoformat() if invite.responded_at else None,
        "team": _serialize_team(invite.team),
    }


def _expire_invitation_if_needed(invite):
    if (
        invite.status == TeamInvitationStatus.PENDING
        and invite.expires_at is not None
        and invite.expires_at <= timezone.now()
    ):
        invite.status = TeamInvitationStatus.EXPIRED
        invite.responded_at = timezone.now()
        invite.save(update_fields=["status", "responded_at"])
    return invite


def _delete_registration_otp(email):
    RegistrationOTP.objects.filter(email=email).delete()


def _user_is_director_of_club(user, club) -> bool:
    return ClubMembership.objects.active().filter(
        user=user,
        club=club,
        role=ClubRole.CLUB_DIRECTOR,
    ).exists()


def _serialize_pending_account_user(user):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }


def _serialize_team_member(membership):
    return {
        "user": _serialize_basic_user(membership.user),
        "membership": {
            "role": membership.role,
            "is_captain": membership.is_captain,
            "is_active": membership.is_active,
            "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
            "left_at": membership.left_at.isoformat() if membership.left_at else None,
        },
    }


def _serialize_parent_relation(relation):
    return {
        "id": relation.id,
        "parent": _serialize_basic_user(relation.parent),
        "player_id": relation.player_id,
        "is_legal_guardian": relation.is_legal_guardian,
        "is_active": relation.is_active,
        "approval_status": relation.approval_status,
    }


def _serialize_player_access_policy(policy):
    return {
        "is_parent_managed": policy.is_parent_managed,
        "can_self_confirm_attendance": policy.can_self_confirm_attendance,
        "can_self_make_payments": policy.can_self_make_payments,
        "can_self_submit_absence_reasons": policy.can_self_submit_absence_reasons,
        "can_self_approve_schedule_confirmations": (
            policy.can_self_approve_schedule_confirmations
        ),
        "can_self_update_emergency_contact": policy.can_self_update_emergency_contact,
    }


def _serialize_notification(notification):
    payload = {
        "id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "category": notification.category,
        "team_name": notification.team.name if notification.team else None,
        "team_id": notification.team_id,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
        "training_session_id": notification.training_session_id,
        "coach_attendance_path": None,
    }
    if (
        notification.category == Notification.Category.ATTENDANCE_INCOMPLETE
        and notification.training_session_id
        and notification.team_id
    ):
        payload["coach_attendance_path"] = coach_attendance_action_path(
            notification.team_id,
            notification.training_session_id,
        )
    return payload


def _serialize_sent_notification_group(group_key, grouped_notifications):
    latest_notification = max(grouped_notifications, key=lambda item: item.created_at)

    return {
        "id": f"sent-{latest_notification.id}",
        "title": latest_notification.title,
        "message": latest_notification.message,
        "category": latest_notification.category,
        "team_name": latest_notification.team.name if latest_notification.team else None,
        "created_at": latest_notification.created_at.isoformat(),
        "recipient_count": len(grouped_notifications),
    }


def _get_team_notification_recipients(team, audience="all"):
    player_ids = set(
        TeamMembership.objects.active()
        .filter(team=team, role=TeamRole.PLAYER)
        .values_list("user_id", flat=True)
    )
    parent_ids = set(
        ParentPlayerRelation.objects.approved()
        .filter(
            player__team_memberships__team=team,
            player__team_memberships__role=TeamRole.PLAYER,
            player__team_memberships__is_active=True,
        )
        .values_list("parent_id", flat=True)
    )

    if audience == "players":
        return player_ids
    if audience == "parents":
        return parent_ids

    return player_ids | parent_ids


def _create_team_notifications(*, team, created_by, title, message, category, audience="all"):
    recipient_ids = _get_team_notification_recipients(team, audience=audience)
    if not recipient_ids:
        return

    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=recipient_id,
                created_by=created_by,
                team=team,
                title=title,
                message=message,
                category=category,
            )
            for recipient_id in recipient_ids
        ]
    )


def _unconfirmed_roster_player_ids(session, team):
    roster_ids = list(
        TeamMembership.objects.active()
        .filter(team=team, role=TeamRole.PLAYER)
        .values_list("user_id", flat=True)
    )
    confirmed_ids = set(
        TrainingSessionConfirmation.objects.filter(training_session=session).values_list("player_id", flat=True)
    )
    return [pid for pid in roster_ids if pid not in confirmed_ids]


def _parent_user_ids_for_players(player_ids):
    if not player_ids:
        return set()
    return set(
        ParentPlayerRelation.objects.approved()
        .filter(player_id__in=player_ids)
        .values_list("parent_id", flat=True)
    )


@csrf_exempt
@require_POST
def register(request):
    if not _password_reset_email_configured():
        return JsonResponse(
            {
                "errors": {
                    "server": "Outbound email is not configured. Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD.",
                }
            },
            status=503,
        )

    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()

    errors = {}

    if not email:
        errors["email"] = "Email is required."
    if not password:
        errors["password"] = "Password is required."
    if not first_name:
        errors["first_name"] = "First name is required."
    if not last_name:
        errors["last_name"] = "Last name is required."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    raw_dob = payload.get("date_of_birth")
    if raw_dob is None or (isinstance(raw_dob, str) and not str(raw_dob).strip()):
        return JsonResponse(
            {"errors": {"date_of_birth": "Date of birth is required."}},
            status=400,
        )

    try:
        date_of_birth = date.fromisoformat(str(raw_dob).strip())
    except ValueError:
        return JsonResponse(
            {"errors": {"date_of_birth": "Use YYYY-MM-DD format."}},
            status=400,
        )

    try:
        validate_password(password)
    except ValidationError as exc:
        if hasattr(exc, "message_dict"):
            return JsonResponse({"errors": exc.message_dict}, status=400)
        messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse({"errors": {"password": messages}}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse(
            {"errors": {"email": "An account with this email already exists."}},
            status=400,
        )

    otp_plain = _generate_numeric_otp()
    expires_at = timezone.now() + timedelta(minutes=_registration_otp_minutes())

    with transaction.atomic():
        RegistrationOTP.objects.update_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": date_of_birth,
                "password_hash": make_password(password),
                "otp_hash": make_password(otp_plain),
                "expires_at": expires_at,
            },
        )

    try:
        _send_registration_otp_email(email, otp_plain, first_name=first_name)
    except Exception:
        logger.exception("Signup verification email failed for %s", email)
        _delete_registration_otp(email)
        return JsonResponse(
            {
                "errors": {
                    "email": "Could not send the verification email. Check server email settings and try again."
                }
            },
            status=503,
        )

    return JsonResponse(
        {
            "message": (
                "We sent a verification code to your email. "
                "Enter it to finish creating your account."
            ),
            "email": email,
        },
        status=200,
    )


@csrf_exempt
@require_POST
def register_verify(request):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    email = (payload.get("email") or "").strip().lower()
    otp = (payload.get("otp") or "").strip()

    errors = {}
    if not email:
        errors["email"] = "Email is required."
    if not otp:
        errors["otp"] = "Verification code is required."
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    registration = (
        RegistrationOTP.objects.filter(email=email, expires_at__gt=timezone.now())
        .order_by("-created_at")
        .first()
    )
    if registration is None or not check_password(otp, registration.otp_hash):
        return JsonResponse(
            {"errors": {"otp": "Invalid or expired verification code."}},
            status=400,
        )

    try:
        with transaction.atomic():
            if User.objects.filter(email=email).exists():
                _delete_registration_otp(email)
                return JsonResponse(
                    {"errors": {"email": "An account with this email already exists."}},
                    status=400,
                )

            user = User(
                email=registration.email,
                first_name=registration.first_name,
                last_name=registration.last_name,
                date_of_birth=registration.date_of_birth,
                verification_status=VerificationStatus.VERIFIED,
            )
            user.password = registration.password_hash
            user.save()
            _delete_registration_otp(email)
    except IntegrityError:
        return JsonResponse(
            {"errors": {"email": "An account with this email already exists."}},
            status=400,
        )

    return _auth_success_response(
        user,
        message="Registration complete. You are now signed in.",
        status=201,
    )


@csrf_exempt
@require_POST
def login(request):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    errors = {}
    if not email:
        errors["email"] = "Email is required."
    if not password:
        errors["password"] = "Password is required."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    user = authenticate(request, email=email, password=password)
    if user is None:
        return JsonResponse(
            {"errors": {"credentials": "Invalid email or password."}},
            status=401,
        )

    return _auth_success_response(user)


@login_required
@require_GET
def directors_pending_users(request):
    if not is_any_club_director(request.user):
        return JsonResponse(
            {"errors": {"authorization": "Only club directors can view pending accounts."}},
            status=403,
        )

    return JsonResponse(
        {
            "pending_users": [],
            "assignable_teams": [],
            "message": "Signup verification is handled by email OTP now. Director approval is no longer required.",
        },
    )


@login_required
@require_POST
@csrf_exempt
def directors_verify_user(request, user_id):
    if not is_any_club_director(request.user):
        return JsonResponse(
            {"errors": {"authorization": "Only club directors can verify accounts."}},
            status=403,
        )

    return JsonResponse(
        {
            "errors": {
                "user": "Email OTP verification is now self-serve. Director approval is no longer used for signup."
            }
        },
        status=410,
    )


@login_required
@require_POST
@csrf_exempt
def directors_reject_user(request, user_id):
    if not is_any_club_director(request.user):
        return JsonResponse(
            {"errors": {"authorization": "Only club directors can reject accounts."}},
            status=403,
        )

    return JsonResponse(
        {
            "errors": {
                "user": "Email OTP verification is now self-serve. Director rejection is no longer used for signup."
            }
        },
        status=410,
    )


def _directory_team_summaries_for_user(user, scope=None):
    club_ids = set(scope.get("club_ids") or []) if scope else set()
    team_ids = set(scope.get("team_ids") or []) if scope else set()
    team_map = {}

    def is_in_scope(team):
        if team is None:
            return False
        if team_ids:
            return team.id in team_ids
        if club_ids:
            return team.club_id in club_ids
        return True

    def add_team(team):
        if not is_in_scope(team):
            return
        if team.id in team_map:
            return
        team_map[team.id] = {
            "id": team.id,
            "name": team.name,
            "short_name": team.short_name or team.name,
            "club_id": team.club_id,
            "club_name": team.club.name if team.club_id else "",
        }

    memberships = getattr(user, "prefetched_active_team_memberships", None)
    if memberships is None:
        memberships = (
            TeamMembership.objects.active()
            .filter(user=user)
            .select_related("team__club")
        )
    for membership in memberships:
        add_team(membership.team)

    relations = getattr(user, "prefetched_approved_player_relationships", None)
    if relations is None:
        relations = (
            ParentPlayerRelation.objects.approved()
            .filter(parent=user)
            .select_related("player")
            .prefetch_related(
                Prefetch(
                    "player__team_memberships",
                    queryset=TeamMembership.objects.active().select_related("team__club"),
                    to_attr="prefetched_active_team_memberships",
                )
            )
        )
    for relation in relations:
        child_memberships = getattr(relation.player, "prefetched_active_team_memberships", None)
        if child_memberships is None:
            child_memberships = (
                TeamMembership.objects.active()
                .filter(user=relation.player)
                .select_related("team__club")
            )
        for membership in child_memberships:
            add_team(membership.team)

    return sorted(team_map.values(), key=lambda item: (item["club_name"], item["name"], item["id"]))


def _serialize_user_directory_row(user, scope=None):
    teams = _directory_team_summaries_for_user(user, scope=scope)
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "verification_status": user.verification_status,
        "role": _canonical_app_role(user) or None,
        "is_staff": user.is_staff,
        "teams": teams,
        "team_short_names": [team["short_name"] for team in teams],
    }


def _scoped_user_directory(request_user):
    if is_staff_user(request_user):
        return (
            User.objects.filter(is_superuser=False),
            {
                "kind": "all",
                "label": "All people in the app",
            },
        )

    director_clubs = list(
        Club.objects.filter(
            memberships__user=request_user,
            memberships__role=ClubRole.CLUB_DIRECTOR,
            memberships__is_active=True,
        )
        .order_by("name", "id")
        .distinct()
    )
    if director_clubs:
        club_ids = [club.id for club in director_clubs]
        users = User.objects.filter(is_superuser=False).filter(
            Q(club_memberships__club_id__in=club_ids, club_memberships__is_active=True)
            | Q(team_memberships__team__club_id__in=club_ids, team_memberships__is_active=True)
            | Q(
                player_relationships__player__team_memberships__team__club_id__in=club_ids,
                player_relationships__is_active=True,
                player_relationships__approval_status=ParentLinkApprovalStatus.APPROVED,
            )
        )
        return (
            users,
            {
                "kind": "club",
                "label": "All people in your club",
                "names": [club.name for club in director_clubs],
                "club_ids": club_ids,
            },
        )

    coached_teams = list(
        Team.objects.filter(
            memberships__user=request_user,
            memberships__role=TeamRole.COACH,
            memberships__is_active=True,
        )
        .select_related("club")
        .order_by("club__name", "name", "id")
        .distinct()
    )
    if coached_teams:
        team_ids = [team.id for team in coached_teams]
        users = User.objects.filter(is_superuser=False).filter(
            Q(team_memberships__team_id__in=team_ids, team_memberships__is_active=True)
            | Q(
                player_relationships__player__team_memberships__team_id__in=team_ids,
                player_relationships__is_active=True,
                player_relationships__approval_status=ParentLinkApprovalStatus.APPROVED,
            )
        )
        return (
            users,
            {
                "kind": "team",
                "label": "All people on your team",
                "names": [team.name for team in coached_teams],
                "team_ids": team_ids,
            },
        )

    return None, None


@login_required
@require_GET
def directors_user_directory(request):
    users, scope = _scoped_user_directory(request.user)
    if users is None:
        return JsonResponse(
            {"errors": {"authorization": "Only club directors or team coaches can view the user directory."}},
            status=403,
        )

    try:
        limit = min(int(request.GET.get("limit", "500")), 2000)
    except ValueError:
        limit = 500

    raw_team_id = (request.GET.get("team_id") or "").strip()
    if raw_team_id:
        try:
            team_id = int(raw_team_id)
        except ValueError:
            return JsonResponse({"errors": {"team_id": "Invalid team id."}}, status=400)

        allowed_team = None
        if scope["kind"] == "all":
            allowed_team = Team.objects.filter(pk=team_id).select_related("club").first()
        elif scope["kind"] == "club":
            allowed_team = (
                Team.objects.filter(
                    pk=team_id,
                    club__memberships__user=request.user,
                    club__memberships__role=ClubRole.CLUB_DIRECTOR,
                    club__memberships__is_active=True,
                )
                .select_related("club")
                .distinct()
                .first()
            )
        elif scope["kind"] == "team":
            allowed_team = (
                Team.objects.filter(
                    pk=team_id,
                    memberships__user=request.user,
                    memberships__role=TeamRole.COACH,
                    memberships__is_active=True,
                )
                .select_related("club")
                .distinct()
                .first()
            )

        if allowed_team is None:
            return JsonResponse(
                {"errors": {"authorization": "You do not have access to that team."}},
                status=403,
            )

        users = users.filter(
            Q(team_memberships__team_id=allowed_team.id, team_memberships__is_active=True)
            | Q(
                player_relationships__player__team_memberships__team_id=allowed_team.id,
                player_relationships__is_active=True,
                player_relationships__approval_status=ParentLinkApprovalStatus.APPROVED,
            )
        )
        scope = {
            "kind": "team",
            "label": "All people on your team",
            "names": [allowed_team.name],
            "team_id": allowed_team.id,
            "club_id": allowed_team.club_id,
            "club_name": allowed_team.club.name if allowed_team.club_id else "",
        }

    users = users.order_by("email", "id").distinct()[:limit]
    users = users.prefetch_related(
        Prefetch(
            "team_memberships",
            queryset=TeamMembership.objects.active().select_related("team__club"),
            to_attr="prefetched_active_team_memberships",
        ),
        Prefetch(
            "player_relationships",
            queryset=ParentPlayerRelation.objects.approved()
            .select_related("player")
            .prefetch_related(
                Prefetch(
                    "player__team_memberships",
                    queryset=TeamMembership.objects.active().select_related("team__club"),
                    to_attr="prefetched_active_team_memberships",
                )
            ),
            to_attr="prefetched_approved_player_relationships",
        ),
    )
    rows = [_serialize_user_directory_row(u, scope=scope) for u in users]
    return JsonResponse({"users": rows, "count": len(rows), "scope": scope})


@login_required
@csrf_exempt
@require_POST
def directors_set_user_account_role(request, user_id):
    if not is_any_club_director(request.user):
        return JsonResponse(
            {"errors": {"authorization": "Only club directors can update account roles."}},
            status=403,
        )

    target = get_object_or_404(User, pk=user_id)
    if target.is_superuser:
        return JsonResponse(
            {"errors": {"user": "Cannot change roles for this account."}},
            status=403,
        )
    if target.is_staff and not is_staff_user(request.user):
        return JsonResponse(
            {"errors": {"user": "Only platform staff can change roles for staff accounts."}},
            status=403,
        )

    payload = _parse_json_request(request) or {}
    raw = payload.get("role")
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return JsonResponse({"errors": {"role": "Role is required."}}, status=400)
    new_role = str(raw).strip().lower()
    if new_role not in AssignedAccountRole.values:
        return JsonResponse(
            {
                "errors": {
                    "role": "Must be one of: director, player, parent, coach.",
                },
            },
            status=400,
        )

    manageable_club_ids = list(
        Club.objects.filter(
            memberships__user=request.user,
            memberships__role=ClubRole.CLUB_DIRECTOR,
            memberships__is_active=True,
        )
        .values_list("id", flat=True)
        .distinct()
    )

    if target.id == request.user.id and new_role != AssignedAccountRole.DIRECTOR:
        if ClubMembership.objects.active().filter(
            user=target,
            role=ClubRole.CLUB_DIRECTOR,
        ).exists():
            return JsonResponse(
                {"errors": {"role": "You cannot remove your own director role."}},
                status=403,
            )

    director_club = None
    if new_role == AssignedAccountRole.DIRECTOR:
        raw_club = payload.get("club_id")
        club_id = None
        if raw_club is not None and str(raw_club).strip() != "":
            try:
                club_id = int(raw_club)
            except (TypeError, ValueError):
                return JsonResponse(
                    {"errors": {"club_id": "Invalid club id."}},
                    status=400,
                )
        if club_id is None:
            if len(manageable_club_ids) == 1:
                club_id = manageable_club_ids[0]
            else:
                return JsonResponse(
                    {
                        "errors": {
                            "club_id": (
                                "club_id is required when promoting someone to director "
                                "and you manage more than one club."
                            ),
                        },
                    },
                    status=400,
                )
        director_club = get_object_or_404(Club, pk=club_id)
        if not can_manage_club(request.user, director_club):
            return JsonResponse(
                {"errors": {"club_id": "You cannot assign directors for this club."}},
                status=403,
            )

    try:
        with transaction.atomic():
            if new_role == AssignedAccountRole.DIRECTOR:
                ClubMembership.objects.assign_director(user=target, club=director_club)
            elif new_role in (
                AssignedAccountRole.PLAYER,
                AssignedAccountRole.PARENT,
                AssignedAccountRole.COACH,
            ):
                for membership in ClubMembership.objects.active().filter(
                    user=target,
                    role=ClubRole.CLUB_DIRECTOR,
                    club_id__in=manageable_club_ids,
                ):
                    ClubMembership.objects.deactivate(membership)
    except IntegrityError:
        return JsonResponse(
            {"errors": {"user": "Could not update role (data conflict). Try again."}},
            status=400,
        )

    target.refresh_from_db()
    return JsonResponse({"user": _serialize_basic_user(target)})


@csrf_exempt
@require_POST
def password_reset_request(request):
    if not _password_reset_email_configured():
        return JsonResponse(
            {
                "errors": {
                    "server": "Outbound email is not configured. Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD.",
                }
            },
            status=503,
        )

    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    email = (payload.get("email") or "").strip().lower()
    if not email:
        return JsonResponse({"errors": {"email": "Email is required."}}, status=400)

    generic_message = {
        "message": "If an account exists for this email, a reset code has been sent."
    }

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse(generic_message, status=200)

    if not user.is_active:
        return JsonResponse(generic_message, status=200)

    PasswordResetOTP.objects.filter(user=user).delete()
    otp_plain = _generate_numeric_otp()
    expires_at = timezone.now() + timedelta(minutes=settings.PASSWORD_RESET_OTP_MINUTES)
    PasswordResetOTP.objects.create(
        user=user,
        otp_hash=make_password(otp_plain),
        expires_at=expires_at,
    )

    try:
        _send_password_reset_otp_email(user, otp_plain)
    except Exception:
        logger.exception("Password reset email failed for %s", user.email)
        PasswordResetOTP.objects.filter(user=user).delete()
        return JsonResponse(
            {
                "errors": {
                    "email": "Could not send the reset email. Check server email settings and try again."
                }
            },
            status=503,
        )

    return JsonResponse(generic_message, status=200)


@csrf_exempt
@require_POST
def password_reset_confirm(request):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    email = (payload.get("email") or "").strip().lower()
    otp = (payload.get("otp") or "").strip()
    new_password = payload.get("new_password") or ""

    errors = {}
    if not email:
        errors["email"] = "Email is required."
    if not otp:
        errors["otp"] = "Verification code is required."
    if not new_password:
        errors["new_password"] = "New password is required."
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    try:
        validate_password(new_password)
    except ValidationError as exc:
        if hasattr(exc, "message_dict"):
            return JsonResponse({"errors": exc.message_dict}, status=400)
        messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse({"errors": {"new_password": messages}}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse(
            {"errors": {"otp": "Invalid or expired verification code."}},
            status=400,
        )

    reset_row = (
        PasswordResetOTP.objects.filter(user=user, expires_at__gt=timezone.now())
        .order_by("-created_at")
        .first()
    )

    if reset_row is None or not check_password(otp, reset_row.otp_hash):
        return JsonResponse(
            {"errors": {"otp": "Invalid or expired verification code."}},
            status=400,
        )

    user.set_password(new_password)
    user.save(update_fields=["password"])
    PasswordResetOTP.objects.filter(user=user).delete()

    return JsonResponse({"message": "Your password has been reset successfully."}, status=200)


@csrf_exempt
@require_POST
def contact_submit(request):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    name = (payload.get("name") or "").strip()
    email_value = (payload.get("email") or "").strip().lower()
    role = (payload.get("role") or "").strip().lower()
    message = (payload.get("message") or "").strip()
    phone = (payload.get("phone") or "").strip()

    errors = {}
    if not name:
        errors["name"] = "Name is required."
    if not email_value:
        errors["email"] = "Email is required."
    else:
        try:
            EmailValidator()(email_value)
        except ValidationError:
            errors["email"] = "Enter a valid email address."

    valid_roles = {choice.value for choice in ContactSubmission.ContactRole}
    if role not in valid_roles:
        errors["role"] = "Select a valid role."

    if not message:
        errors["message"] = "Message is required."

    if phone and len(phone) > 40:
        errors["phone"] = "Phone number is too long."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    row = ContactSubmission.objects.create(
        name=name,
        email=email_value,
        role=role,
        message=message,
        phone=phone,
    )
    _dispatch_contact_submission_notification(row)
    return JsonResponse(
        {
            "id": row.id,
            "message": "Thanks — we received your message and will get back to you soon.",
        },
        status=201,
    )


@login_required
@require_GET
def me(request):
    owned_clubs = [
        _serialize_club(membership.club)
        for membership in ClubMembership.objects.active()
        .filter(user=request.user, role=ClubRole.CLUB_DIRECTOR)
        .select_related("club")
    ]
    director_teams = [
        {
            **_serialize_team_summary(team),
            "can_manage_schedule": can_manage_team(request.user, team),
            "can_manage_training": can_manage_team(request.user, team),
        }
        for team in Team.objects.filter(
            club__memberships__user=request.user,
            club__memberships__role=ClubRole.CLUB_DIRECTOR,
            club__memberships__is_active=True,
        )
        .select_related("club")
        .distinct()
    ]
    coached_teams = [
        {
            **_serialize_team_summary(membership.team),
            "can_manage_schedule": can_manage_team(request.user, membership.team),
            "can_manage_training": can_manage_team(request.user, membership.team),
        }
        for membership in TeamMembership.objects.active()
        .filter(user=request.user, role=TeamRole.COACH)
        .select_related("team__club")
    ]
    player_teams = [
        {
            **_serialize_team_summary(membership.team),
            "can_manage_schedule": False,
            "can_manage_training": False,
        }
        for membership in TeamMembership.objects.active()
        .filter(user=request.user, role=TeamRole.PLAYER)
        .select_related("team__club")
    ]
    children = []
    pending_parent_links = []
    for rel in (
        ParentPlayerRelation.objects.pending()
        .filter(parent=request.user)
        .select_related("player")
    ):
        pending_parent_links.append(
            {
                "relation_id": rel.id,
                "player": _serialize_basic_user(rel.player),
            }
        )

    parent_relations = (
        ParentPlayerRelation.objects.approved()
        .filter(parent=request.user)
        .select_related("player")
    )

    for relation in parent_relations:
        child_teams = [
            {
                **_serialize_team_summary(membership.team),
                "can_manage_schedule": False,
                "can_manage_training": False,
            }
            for membership in TeamMembership.objects.active()
            .filter(user=relation.player, role=TeamRole.PLAYER)
            .select_related("team__club")
        ]
        children.append(
            {
                "user": _serialize_basic_user(relation.player),
                "teams": child_teams,
            }
        )

    return JsonResponse(
        {
            "user": _serialize_basic_user(request.user),
            "account_profile": _build_account_profile(request.user),
            "is_director_or_staff": is_any_club_director(request.user),
            "viewer_is_staff": request.user.is_staff,
            "owned_clubs": owned_clubs,
            "director_teams": director_teams,
            "coached_teams": coached_teams,
            "player_teams": player_teams,
            "children": children,
            "pending_parent_links": pending_parent_links,
        }
    )


@login_required
@require_GET
def member_hub_dashboard(request):
    """Aggregated parent/player home dashboard (profile, fees, progress, next session)."""
    from .member_dashboard import build_member_hub_dashboard_payload

    raw = request.GET.get("for_player_id")
    for_player_id = None
    if raw not in (None, ""):
        try:
            for_player_id = int(raw)
        except (TypeError, ValueError):
            return JsonResponse({"errors": {"for_player_id": "A valid numeric player id is required."}}, status=400)

    payload, status = build_member_hub_dashboard_payload(request.user, for_player_id=for_player_id)
    return JsonResponse(payload, status=status)


@login_required
@require_GET
def parent_child_attendance_history(request):
    """EP-23: Linked children's training session attendance for assigned parent accounts only."""
    if _canonical_app_role(request.user) != AssignedAccountRole.PARENT:
        return JsonResponse(
            {"errors": {"authorization": "Only accounts with the parent role can view child attendance history."}},
            status=403,
        )

    relations = list(
        ParentPlayerRelation.objects.approved()
        .filter(parent=request.user)
        .select_related("player")
        .order_by("player_id")
    )
    if not relations:
        return JsonResponse(
            {
                "linked_children": [],
                "records": [],
                "attendance_summaries": [],
                "message": "No approved parent link to a player account yet.",
            }
        )

    child_users = [rel.player for rel in relations]
    child_ids = [u.id for u in child_users]

    memberships = (
        TeamMembership.objects.active()
        .filter(user_id__in=child_ids, role=TeamRole.PLAYER)
        .values_list("user_id", "team_id")
    )
    teams_by_child = defaultdict(set)
    for user_id, team_id in memberships:
        teams_by_child[user_id].add(team_id)

    all_team_ids = set()
    for team_set in teams_by_child.values():
        all_team_ids |= team_set
    if not all_team_ids:
        return JsonResponse(
            {
                "linked_children": [_serialize_basic_user(u) for u in child_users],
                "records": [],
                "attendance_summaries": [],
                "message": "Linked players are not on an active team roster yet.",
            }
        )

    sessions = (
        TrainingSession.objects.filter(team_id__in=all_team_ids)
        .select_related("team", "team__club")
        .order_by("-scheduled_date", "-start_time", "-id")
    )

    session_list = list(sessions)
    session_ids = [s.id for s in session_list]

    confirmation_map = {}
    if session_ids:
        for conf in TrainingSessionConfirmation.objects.filter(
            training_session_id__in=session_ids,
            player_id__in=child_ids,
        ).select_related("confirmed_by"):
            confirmation_map[(conf.training_session_id, conf.player_id)] = conf

    records = []
    for session in session_list:
        for child in child_users:
            if session.team_id not in teams_by_child[child.id]:
                continue
            conf = confirmation_map.get((session.id, child.id))
            status_code, status_label = attendance_status(session, conf is not None)
            records.append(
                {
                    "session_id": session.id,
                    "team": {
                        "id": session.team_id,
                        "name": session.team.name,
                        "club_name": session.team.club.name if session.team.club_id else "",
                    },
                    "child": _serialize_basic_user(child),
                    "scheduled_date": session.scheduled_date.isoformat(),
                    "start_time": session.start_time.strftime("%H:%M"),
                    "end_time": session.end_time.strftime("%H:%M"),
                    "location": session.location,
                    "title": session.title,
                    "description": session.notes or "",
                    "session_type": session.session_type,
                    "session_type_label": session.get_session_type_display(),
                    "session_status": session.status,
                    "session_status_label": session.get_status_display(),
                    "attendance_status": status_code,
                    "attendance_label": status_label,
                    "confirmed_at": conf.confirmed_at.isoformat() if conf else None,
                }
            )

    summary_today = timezone.localdate()
    summary_start = summary_today - timedelta(days=84)
    # Include upcoming sessions in summary counts (pending / upcoming confirmed) while
    # closed-session rates still use only dates strictly before today (see CALCULATION_SUMMARY_TEXT).
    summary_end = summary_today + timedelta(days=730)
    teams_cached = {
        t.id: t for t in Team.objects.filter(id__in=all_team_ids).select_related("club")
    }
    attendance_summaries = []
    for child in child_users:
        for tid in teams_by_child[child.id]:
            team = teams_cached.get(tid)
            if team is None:
                continue
            built = build_player_team_summary(
                team,
                child.id,
                start_date=summary_start,
                end_date=summary_end,
                last_n_sessions=None,
            )
            if not built:
                continue
            attendance_summaries.append(
                {
                    "child": _serialize_basic_user(child),
                    "team": {"id": team.id, "name": team.name, "club_name": team.club.name},
                    "calculation_summary": CALCULATION_SUMMARY_TEXT,
                    "filters": built["filters"],
                    "today": built["today"],
                    "metrics": built["player"],
                }
            )

    return JsonResponse(
        {
            "linked_children": [_serialize_basic_user(u) for u in child_users],
            "records": records,
            "attendance_summaries": attendance_summaries,
        }
    )


def _director_managed_club_ids(user):
    return set(
        Club.objects.filter(
            memberships__user=user,
            memberships__role=ClubRole.CLUB_DIRECTOR,
            memberships__is_active=True,
        ).values_list("id", flat=True)
    )


def _pending_parent_links_queryset_for_director(user):
    """Queryset of pending parent–player links for the director approval queue."""
    base = ParentPlayerRelation.objects.pending().select_related("parent", "player")
    club_ids = _director_managed_club_ids(user)

    player_in_managed_club = TeamMembership.objects.filter(
        user_id=OuterRef("player_id"),
        is_active=True,
        team__club_id__in=club_ids,
    )
    parent_in_managed_club = TeamMembership.objects.filter(
        user_id=OuterRef("parent_id"),
        is_active=True,
        team__club_id__in=club_ids,
    )
    child_fees_in_managed_club = PlayerFeeRecord.objects.filter(
        player_id=OuterRef("player_id"),
        club_id__in=club_ids,
    )

    if club_ids:
        return base.filter(
            Q(Exists(player_in_managed_club))
            | Q(Exists(parent_in_managed_club))
            | Q(Exists(child_fees_in_managed_club)),
        )

    if is_staff_user(user):
        p_tm = TeamMembership.objects.filter(user_id=OuterRef("player_id"), is_active=True)
        par_tm = TeamMembership.objects.filter(user_id=OuterRef("parent_id"), is_active=True)
        p_fee = PlayerFeeRecord.objects.filter(player_id=OuterRef("player_id"))
        return base.filter(Q(Exists(p_tm)) | Q(Exists(par_tm)) | Q(Exists(p_fee)))

    return ParentPlayerRelation.objects.none()


def _director_may_resolve_parent_link_request(user, rel) -> bool:
    """Whether this user may approve or reject the given pending link."""
    if is_staff_user(user):
        return (
            TeamMembership.objects.active()
            .filter(user_id__in=[rel.player_id, rel.parent_id])
            .exists()
            or PlayerFeeRecord.objects.filter(player_id=rel.player_id).exists()
        )
    club_ids = _director_managed_club_ids(user)
    if not club_ids:
        return False
    if PlayerFeeRecord.objects.filter(player_id=rel.player_id, club_id__in=club_ids).exists():
        return True
    return TeamMembership.objects.active().filter(
        user_id__in=[rel.player_id, rel.parent_id],
        team__club_id__in=club_ids,
    ).exists()


def _context_team_for_parent_link_row(rel, club_ids, *, staff_viewer: bool):
    """Club/team label for a pending row from memberships in scope."""
    users = [rel.player_id, rel.parent_id]
    qs = (
        Team.objects.filter(memberships__user_id__in=users, memberships__is_active=True)
        .select_related("club")
        .distinct()
    )
    if club_ids:
        qs = qs.filter(club_id__in=club_ids)
    elif not staff_viewer:
        return None
    return qs.order_by("id").first()


@login_required
@require_GET
def directors_pending_parent_links(request):
    if not is_any_club_director(request.user):
        return JsonResponse(
            {"errors": {"authorization": "Only club directors can view parent link requests."}},
            status=403,
        )
    rows = _pending_parent_links_queryset_for_director(request.user).order_by("id")
    club_ids = _director_managed_club_ids(request.user)
    staff = is_staff_user(request.user)
    out = []
    for rel in rows:
        team = _context_team_for_parent_link_row(rel, club_ids, staff_viewer=staff)
        out.append(
            {
                "relation": _serialize_parent_relation(rel),
                "player": _serialize_basic_user(rel.player),
                "club_name": team.club.name if team else None,
                "team_name": team.name if team else None,
            }
        )
    return JsonResponse({"requests": out})


@login_required
@csrf_exempt
@require_POST
def directors_resolve_parent_link(request, relation_id):
    payload = _parse_json_request(request) or {}
    action = (payload.get("action") or "").strip().lower()
    if action not in ("approve", "reject"):
        return JsonResponse(
            {"errors": {"action": 'Send JSON {"action": "approve"} or {"action": "reject"}.'}},
            status=400,
        )
    if not is_any_club_director(request.user):
        return JsonResponse(
            {"errors": {"authorization": "Only club directors can resolve parent link requests."}},
            status=403,
        )
    rel = get_object_or_404(
        ParentPlayerRelation.objects.pending().select_related("parent", "player"),
        pk=relation_id,
    )
    if not _director_may_resolve_parent_link_request(request.user, rel):
        return JsonResponse(
            {"errors": {"authorization": "You cannot manage this link request."}},
            status=403,
        )
    if action == "approve":
        rel.approval_status = ParentLinkApprovalStatus.APPROVED
        rel.save(update_fields=["approval_status"])
    else:
        rel.approval_status = ParentLinkApprovalStatus.REJECTED
        rel.is_active = False
        rel.save(update_fields=["approval_status", "is_active"])
    return JsonResponse({"relation": _serialize_parent_relation(rel)})


@login_required
@csrf_exempt
@require_POST
def request_parent_link_to_player(request):
    """Parent requests to be linked to a player (child); requires director approval."""
    payload = _parse_json_request(request) or {}
    raw = payload.get("player_id")
    try:
        player_id = int(raw)
    except (TypeError, ValueError):
        return JsonResponse({"errors": {"player_id": "A valid player user ID is required."}}, status=400)

    player = get_object_or_404(User, pk=player_id)
    if player.id == request.user.id:
        return JsonResponse({"errors": {"player_id": "You cannot link to yourself as a parent."}}, status=400)

    existing = ParentPlayerRelation.objects.filter(
        parent=request.user,
        player=player,
    ).first()
    if existing and existing.is_active and existing.approval_status == ParentLinkApprovalStatus.APPROVED:
        return JsonResponse(
            {"errors": {"player_id": "You are already linked to this player."}},
            status=400,
        )
    if existing and existing.is_active and existing.approval_status == ParentLinkApprovalStatus.PENDING:
        return JsonResponse(
            {
                "message": "Your link request is already pending director approval.",
                "relation": _serialize_parent_relation(existing),
            },
            status=200,
        )

    relation, created = ParentPlayerRelation.objects.link(
        parent=request.user,
        player=player,
        is_legal_guardian=bool(payload.get("is_legal_guardian", False)),
        approval_status=ParentLinkApprovalStatus.PENDING,
    )
    return JsonResponse(
        {
            "message": (
                "Your link request was submitted. A club director must approve it before you can manage that "
                "player's payments."
            ),
            "relation": _serialize_parent_relation(relation),
        },
        status=201 if created else 200,
    )


@login_required
@require_GET
def view_team_members(request, team_id):
    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    if not can_view_team(request.user, team):
        return JsonResponse({"errors": {"team": "You do not have access to this team."}}, status=403)

    memberships = (
        TeamMembership.objects.active()
        .filter(team=team)
        .select_related("user")
        .order_by("role", "user__first_name", "user__last_name", "user__email")
    )
    return JsonResponse(
        {
            "team": _serialize_team(team),
            "members": [_serialize_team_member(m) for m in memberships],
            "can_add_player": can_add_team_member(request.user, team, TeamRole.PLAYER),
            "can_add_coach": can_add_team_member(request.user, team, TeamRole.COACH),
            "can_manage_team": can_manage_team(request.user, team),
        }
    )


@login_required
@require_http_methods(["GET", "PUT"])
@csrf_exempt
def team_schedule(request, team_id):
    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)

    if not can_view_team(request.user, team):
        return JsonResponse({"errors": {"team": "You do not have access to this team."}}, status=403)

    if request.method == "GET":
        week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        entries = TeamScheduleEntry.objects.filter(team=team)
        return JsonResponse(
            {
                "team": _serialize_team(team),
                "can_manage_schedule": can_manage_team(request.user, team),
                "week_start": week_start.isoformat(),
                "entries": [_serialize_schedule_entry(entry, week_start) for entry in entries],
            }
        )

    if not can_manage_team(request.user, team):
        return JsonResponse({"errors": {"team": "Only coaches or directors can manage schedules."}}, status=403)

    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    try:
        entries = _parse_schedule_entries(payload.get("entries", []))
    except ValidationError as exc:
        if hasattr(exc, "message_dict"):
            return JsonResponse({"errors": exc.message_dict}, status=400)
        return JsonResponse({"errors": {"entries": exc.messages}}, status=400)

    TeamScheduleEntry.objects.filter(team=team).delete()
    TeamScheduleEntry.objects.bulk_create(
        [
            TeamScheduleEntry(
                team=team,
                activity_name=entry["activity_name"],
                weekday=entry["weekday"],
                start_time=entry["start_time"],
                end_time=entry["end_time"],
                location=entry["location"],
                created_by=request.user,
            )
            for entry in entries
        ]
    )

    week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
    saved_entries = TeamScheduleEntry.objects.filter(team=team)
    _create_team_notifications(
        team=team,
        created_by=request.user,
        title=f"{team.name} schedule updated",
        message="The weekly schedule has been updated. Open the schedule to see the latest details.",
        category=Notification.Category.SCHEDULE,
        audience="all",
    )
    return JsonResponse(
        {
            "message": "Schedule saved successfully.",
            "team": _serialize_team(team),
            "can_manage_schedule": True,
            "week_start": week_start.isoformat(),
            "entries": [_serialize_schedule_entry(entry, week_start) for entry in saved_entries],
        }
    )


@login_required
@require_http_methods(["GET", "POST"])
@csrf_exempt
def team_training_sessions(request, team_id):
    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)

    if not can_view_team(request.user, team):
        return JsonResponse({"errors": {"team": "You do not have access to this team."}}, status=403)

    player_memberships = list(
        TeamMembership.objects.active()
        .filter(team=team, role=TeamRole.PLAYER)
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "user__email")
    )

    if request.method == "GET":
        sessions = TrainingSession.objects.filter(team=team).prefetch_related(
            "confirmations__player",
            "confirmations__confirmed_by",
        )
        if not can_manage_team(request.user, team):
            sessions = sessions.exclude(status=TrainingSession.Status.CANCELLED)

        return JsonResponse(
            {
                "team": _serialize_team(team),
                "can_manage_training": can_manage_team(request.user, team),
                "sessions": [
                    _serialize_training_session(session, request.user, team, player_memberships)
                    for session in sessions
                ],
            }
        )

    if not can_manage_team(request.user, team):
        return JsonResponse(
            {"errors": {"team": "Only coaches or directors can create training sessions."}},
            status=403,
        )

    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    try:
        session_data = _parse_training_session_payload(payload)
    except ValidationError as exc:
        if hasattr(exc, "message_dict"):
            return JsonResponse({"errors": exc.message_dict}, status=400)
        return JsonResponse({"errors": {"body": exc.messages}}, status=400)

    session = TrainingSession.objects.create(
        team=team,
        created_by=request.user,
        **session_data,
    )
    session = (
        TrainingSession.objects.filter(pk=session.pk)
        .prefetch_related("confirmations__player", "confirmations__confirmed_by")
        .get()
    )
    _create_team_notifications(
        team=team,
        created_by=request.user,
        title=f"New {session.get_session_type_display().lower()} session for {team.name}",
        message=(
            f"{session.title} was scheduled for {session.scheduled_date.isoformat()} "
            f"from {session.start_time.strftime('%H:%M')} to {session.end_time.strftime('%H:%M')}."
        ),
        category=Notification.Category.SESSION,
        audience="all",
    )

    return JsonResponse(
        {
            "message": "Training session created successfully.",
            "session": _serialize_training_session(session, request.user, team, player_memberships),
        },
        status=201,
    )


@login_required
@require_http_methods(["PUT", "DELETE"])
@csrf_exempt
def manage_training_session(request, session_id):
    session = get_object_or_404(
        TrainingSession.objects.select_related("team__club"),
        pk=session_id,
    )
    team = session.team

    if not can_manage_team(request.user, team):
        return JsonResponse(
            {"errors": {"team": "Only coaches or directors can manage training sessions."}},
            status=403,
        )

    player_memberships = list(
        TeamMembership.objects.active()
        .filter(team=team, role=TeamRole.PLAYER)
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "user__email")
    )

    if request.method == "DELETE":
        session.status = TrainingSession.Status.CANCELLED
        session.save(update_fields=["status", "updated_at"])
        session = (
            TrainingSession.objects.filter(pk=session.pk)
            .prefetch_related("confirmations__player", "confirmations__confirmed_by")
            .get()
        )
        sync_incomplete_attendance_notifications_for_session_id(session.pk)
        _create_team_notifications(
            team=team,
            created_by=request.user,
            title=f"{session.title} cancelled",
            message=f"The session scheduled for {session.scheduled_date.isoformat()} has been cancelled.",
            category=Notification.Category.SESSION,
            audience="all",
        )
        return JsonResponse(
            {
                "message": "Training session cancelled successfully.",
                "session": _serialize_training_session(session, request.user, team, player_memberships),
            }
        )

    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    try:
        session_data = _parse_training_session_payload(payload)
    except ValidationError as exc:
        if hasattr(exc, "message_dict"):
            return JsonResponse({"errors": exc.message_dict}, status=400)
        return JsonResponse({"errors": {"body": exc.messages}}, status=400)

    original_values = {
        "title": session.title,
        "scheduled_date": session.scheduled_date,
        "start_time": session.start_time,
        "end_time": session.end_time,
        "location": session.location,
        "opponent": session.opponent,
        "team_id": session.team_id,
        "notes": session.notes,
    }

    for field, value in session_data.items():
        setattr(session, field, value)
    session.save()
    session = (
        TrainingSession.objects.filter(pk=session.pk)
        .prefetch_related("confirmations__player", "confirmations__confirmed_by")
        .get()
    )
    sync_incomplete_attendance_notifications_for_session_id(session.pk)
    changed_labels = []
    if original_values["scheduled_date"] != session.scheduled_date:
        changed_labels.append("date")
    if original_values["start_time"] != session.start_time or original_values["end_time"] != session.end_time:
        changed_labels.append("time")
    if original_values["location"] != session.location:
        changed_labels.append("location")
    if original_values["opponent"] != session.opponent:
        changed_labels.append("opponent")
    if original_values["notes"] != session.notes:
        changed_labels.append("details")
    if original_values["title"] != session.title:
        changed_labels.append("session")

    _create_team_notifications(
        team=team,
        created_by=request.user,
        title=f"{session.title} updated",
        message=(
            "Updated fields: " + ", ".join(changed_labels)
            if changed_labels
            else "Session details were updated."
        ),
        category=Notification.Category.SESSION,
        audience="all",
    )

    return JsonResponse(
        {
            "message": "Training session updated successfully.",
            "session": _serialize_training_session(session, request.user, team, player_memberships),
        }
    )


@login_required
@require_http_methods(["DELETE"])
@csrf_exempt
def clear_training_session(request, session_id):
    session = get_object_or_404(
        TrainingSession.objects.select_related("team__club"),
        pk=session_id,
    )
    team = session.team

    if not can_manage_team(request.user, team):
        return JsonResponse(
            {"errors": {"team": "Only coaches or directors can clear training sessions."}},
            status=403,
        )

    if session.status != TrainingSession.Status.CANCELLED:
        return JsonResponse(
            {"errors": {"session": "Only cancelled sessions can be cleared."}},
            status=400,
        )

    session.delete()
    return JsonResponse({"message": "Session cleared successfully.", "session_id": session_id})


@login_required
@require_POST
@csrf_exempt
def confirm_training_session(request, session_id):
    session = get_object_or_404(
        TrainingSession.objects.select_related("team__club"),
        pk=session_id,
    )
    team = session.team

    if not can_view_team(request.user, team):
        return JsonResponse({"errors": {"team": "You do not have access to this team."}}, status=403)

    if session.status == TrainingSession.Status.CANCELLED:
        return JsonResponse({"errors": {"session": "Cancelled sessions cannot be confirmed."}}, status=400)

    payload = _parse_json_request(request)
    if payload is None:
        payload = {}

    requested_player_id = payload.get("player_id")

    player_memberships = list(
        TeamMembership.objects.active()
        .filter(team=team, role=TeamRole.PLAYER)
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "user__email")
    )
    team_players = {membership.user_id: membership.user for membership in player_memberships}

    target_player = None

    if requested_player_id:
        try:
            target_player = team_players[int(requested_player_id)]
        except (KeyError, TypeError, ValueError):
            return JsonResponse({"errors": {"player_id": "Player is not on this team."}}, status=400)

    if target_player is None and request.user.id in team_players:
        target_player = request.user

    if target_player is None:
        return JsonResponse(
            {"errors": {"player_id": "A valid player must be provided for confirmation."}},
            status=400,
        )

    can_confirm = (
        request.user == target_player and _can_player_self_confirm_training(target_player)
    ) or _can_parent_confirm_training(request.user, target_player, team)

    if not can_confirm:
        return JsonResponse(
            {"errors": {"confirmation": "You cannot confirm attendance for this player."}},
            status=403,
        )

    TrainingSessionConfirmation.objects.update_or_create(
        training_session=session,
        player=target_player,
        defaults={"confirmed_by": request.user},
    )

    session = (
        TrainingSession.objects.filter(pk=session.pk)
        .prefetch_related("confirmations__player", "confirmations__confirmed_by")
        .get()
    )

    sync_incomplete_attendance_notifications_for_session_id(session.pk)

    return JsonResponse(
        {
            "message": "Attendance confirmed successfully.",
            "session": _serialize_training_session(session, request.user, team, player_memberships),
        }
    )


@login_required
@require_GET
def coach_training_session_attendance(request, session_id):
    """EP-25: session roster + attendance for coaches and club directors (planning)."""
    session = get_object_or_404(
        TrainingSession.objects.select_related("team__club")
        .prefetch_related("confirmations__player", "confirmations__confirmed_by"),
        pk=session_id,
    )
    team = session.team
    if not can_manage_team(request.user, team):
        return JsonResponse(
            {
                "errors": {
                    "authorization": (
                        "Only coaches or club directors for this team can view session attendance for planning."
                    )
                }
            },
            status=403,
        )

    player_memberships = list(
        TeamMembership.objects.active()
        .filter(team=team, role=TeamRole.PLAYER)
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "user__email")
    )
    return JsonResponse(
        {
            "session": _serialize_coach_training_session_attendance(
                session, team, player_memberships
            ),
        }
    )


def _parse_attendance_summary_query_params(request, *, default_days_back: int = 84):
    """Shared query parsing for attendance summary and analytics endpoints (EP-27)."""
    today = timezone.localdate()
    start_date = end_date = None
    last_n_sessions = None

    start_raw = (request.GET.get("start_date") or "").strip()
    end_raw = (request.GET.get("end_date") or "").strip()
    if start_raw:
        try:
            start_date = date.fromisoformat(start_raw)
        except ValueError:
            return None, None, None, JsonResponse({"errors": {"start_date": "Use YYYY-MM-DD."}}, status=400)
    if end_raw:
        try:
            end_date = date.fromisoformat(end_raw)
        except ValueError:
            return None, None, None, JsonResponse({"errors": {"end_date": "Use YYYY-MM-DD."}}, status=400)

    last_n_raw = (request.GET.get("last_n_sessions") or "").strip()
    if last_n_raw:
        try:
            last_n_sessions = int(last_n_raw)
        except ValueError:
            return None, None, None, JsonResponse({"errors": {"last_n_sessions": "Must be an integer."}}, status=400)
        if last_n_sessions < 1 or last_n_sessions > 500:
            return None, None, None, JsonResponse(
                {"errors": {"last_n_sessions": "Use a value between 1 and 500."}},
                status=400,
            )

    eff_start = start_date if start_date is not None else today - timedelta(days=default_days_back)
    eff_end = end_date if end_date is not None else today
    if eff_start > eff_end:
        return None, None, None, JsonResponse(
            {"errors": {"start_date": "start_date must be on or before end_date."}},
            status=400,
        )

    return eff_start, eff_end, last_n_sessions, None


@login_required
@require_GET
def team_attendance_analytics(request, team_id):
    """EP-26: attendance rates over time for coaches / directors who can manage the team."""
    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    if not can_manage_team(request.user, team):
        return JsonResponse(
            {
                "errors": {
                    "authorization": (
                        "Only coaches or club directors for this team can view attendance analytics."
                    )
                }
            },
            status=403,
        )

    eff_start, eff_end, last_n_sessions, err = _parse_attendance_summary_query_params(request)
    if err:
        return err

    grouping = (request.GET.get("grouping") or "week").strip()

    payload = build_team_attendance_analytics(
        team,
        start_date=eff_start,
        end_date=eff_end,
        grouping=grouping,
        last_n_sessions=last_n_sessions,
    )
    return JsonResponse(payload)


@login_required
@require_GET
def team_attendance_summary(request, team_id):
    """EP-27: compact team roll-up (no per-player rows) for dashboards."""
    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    if not can_manage_team(request.user, team):
        return JsonResponse(
            {
                "errors": {
                    "authorization": (
                        "Only coaches or club directors for this team can view attendance summaries."
                    )
                }
            },
            status=403,
        )

    eff_start, eff_end, last_n_sessions, err = _parse_attendance_summary_query_params(request)
    if err:
        return err

    payload = build_team_compact_summary(
        team,
        start_date=eff_start,
        end_date=eff_end,
        last_n_sessions=last_n_sessions,
    )
    return JsonResponse(payload)


@login_required
@require_GET
def player_team_attendance_summary(request, team_id, player_id):
    """EP-27: per-player summary for one team (player self, linked parent, coach/director)."""
    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    target = get_object_or_404(User, pk=player_id)

    allowed = False
    if request.user.id == target.id and is_team_player(target, team):
        allowed = True
    elif is_parent_of_player_on_team(request.user, target, team):
        allowed = True
    elif can_manage_team(request.user, team):
        allowed = True
    elif is_staff_user(request.user):
        allowed = True

    if not allowed:
        return JsonResponse(
            {
                "errors": {
                    "authorization": "You cannot view this player's attendance summary for this team."
                }
            },
            status=403,
        )

    eff_start, eff_end, last_n_sessions, err = _parse_attendance_summary_query_params(request)
    if err:
        return err

    payload = build_player_team_summary(
        team,
        player_id,
        start_date=eff_start,
        end_date=eff_end,
        last_n_sessions=last_n_sessions,
    )
    if payload is None:
        return JsonResponse(
            {"errors": {"player": "Player is not on this team's active roster."}},
            status=404,
        )
    return JsonResponse(payload)


@login_required
@require_GET
def coach_team_dashboard(request, team_id):
    """Aggregated coach dashboard KPIs, chart metrics, roster stats, and feedback (DB-backed)."""
    from .coach_dashboard import build_coach_team_dashboard

    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    if not can_manage_team(request.user, team):
        return JsonResponse(
            {
                "errors": {
                    "authorization": (
                        "Only coaches or club directors for this team can view the coach dashboard."
                    )
                }
            },
            status=403,
        )
    payload = build_coach_team_dashboard(team=team)
    return JsonResponse(payload)


@login_required
@require_GET
def notifications(request):
    notification_items = list(
        Notification.objects.filter(recipient=request.user)
        .select_related("team", "training_session")
    )
    unread_count = sum(1 for item in notification_items if not item.is_read)
    sent_items = []
    team_id = request.GET.get("team_id")

    if team_id:
        try:
            team = Team.objects.select_related("club").get(pk=int(team_id))
        except (Team.DoesNotExist, ValueError, TypeError):
            team = None

        if team and can_manage_team(request.user, team):
            sent_notifications = (
                Notification.objects.filter(created_by=request.user, team=team)
                .select_related("team")
                .order_by("-created_at", "-id")
            )
            grouped_notifications = {}

            for item in sent_notifications:
                group_key = (
                    item.title,
                    item.message,
                    item.category,
                    item.team_id,
                    item.created_at.replace(microsecond=0),
                )
                grouped_notifications.setdefault(group_key, []).append(item)

            sent_items = [
                _serialize_sent_notification_group(group_key, items)
                for group_key, items in grouped_notifications.items()
            ]
            sent_items.sort(key=lambda item: item["created_at"], reverse=True)

    return JsonResponse(
        {
            "unread_count": unread_count,
            "items": [_serialize_notification(item) for item in notification_items],
            "sent_items": sent_items,
        }
    )


@login_required
@require_POST
@csrf_exempt
def mark_notifications_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"message": "Notifications marked as read."})


@login_required
@require_POST
@csrf_exempt
def send_team_notification(request):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    team_id = payload.get("team_id")
    audience = (payload.get("audience") or "all").strip()
    title = (payload.get("title") or "").strip()
    message = (payload.get("message") or "").strip()

    errors = {}
    if not team_id:
        errors["team_id"] = "team_id is required."
    if audience not in ["all", "players", "parents"]:
        errors["audience"] = "Audience must be all, players, or parents."
    if not title:
        errors["title"] = "Title is required."
    if not message:
        errors["message"] = "Message is required."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    if not can_manage_team(request.user, team):
        return JsonResponse(
            {"errors": {"team": "Only coaches or directors can send team notifications."}},
            status=403,
        )

    _create_team_notifications(
        team=team,
        created_by=request.user,
        title=title,
        message=message,
        category=Notification.Category.MANUAL,
        audience=audience,
    )

    return JsonResponse({"message": "Notification sent successfully."}, status=201)


@login_required
@require_POST
@csrf_exempt
def remind_unconfirmed_training_session(request, session_id):
    """
    In-app reminders only for roster players (and optionally parents) who have not confirmed.
    Parents are excluded for cancelled sessions (rejected) and for sessions that have already ended
    (past practices); players who already confirmed never receive this reminder.
    """
    session = get_object_or_404(
        TrainingSession.objects.select_related("team__club"),
        pk=session_id,
    )
    team = session.team
    if not can_manage_team(request.user, team):
        return JsonResponse(
            {
                "errors": {
                    "authorization": (
                        "Only coaches or club directors for this team can send attendance reminders."
                    )
                }
            },
            status=403,
        )
    if session.status == TrainingSession.Status.CANCELLED:
        return JsonResponse(
            {"errors": {"session": "Reminders are not sent for cancelled sessions."}},
            status=400,
        )

    payload = _parse_json_request(request)
    if payload is None:
        payload = {}
    audience = (payload.get("audience") or "all").strip()
    if audience not in ("all", "players", "parents"):
        return JsonResponse(
            {"errors": {"audience": "Audience must be all, players, or parents."}},
            status=400,
        )

    unconfirmed_ids = _unconfirmed_roster_player_ids(session, team)
    session_ended = training_session_has_ended(session)
    player_recipients = set()
    parent_recipients = set()
    if audience in ("players", "all"):
        player_recipients.update(unconfirmed_ids)
    if audience in ("parents", "all") and not session_ended:
        parent_recipients.update(_parent_user_ids_for_players(unconfirmed_ids))
    all_recipients = player_recipients | parent_recipients

    if not all_recipients:
        return JsonResponse(
            {
                "message": (
                    "No reminders sent: everyone on the roster has confirmed, or there are no eligible parents "
                    "(parents are not notified for past sessions)."
                ),
                "recipient_count": 0,
                "player_recipient_count": 0,
                "parent_recipient_count": 0,
            },
            status=200,
        )

    title = f"Please confirm attendance: {session.title}"
    loc = f" Location: {session.location}." if session.location else ""
    message = (
        f'Please confirm attendance for "{session.title}" on {session.scheduled_date.isoformat()} '
        f"({session.start_time.strftime('%H:%M')}–{session.end_time.strftime('%H:%M')}).{loc} "
        "Players: open My sessions. Parents: open Attendance. Thank you."
    )
    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=rid,
                created_by=request.user,
                team=team,
                title=title,
                message=message,
                category=Notification.Category.MANUAL,
            )
            for rid in all_recipients
        ]
    )
    return JsonResponse(
        {
            "message": "Reminder notifications sent.",
            "recipient_count": len(all_recipients),
            "player_recipient_count": len(player_recipients),
            "parent_recipient_count": len(parent_recipients),
        },
        status=201,
    )


@csrf_exempt
@login_required
@require_POST
def add_team_member(request, team_id):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    team = get_object_or_404(Team, pk=team_id)
    target_user_id = payload.get("user_id")
    role = (payload.get("role") or "").strip()

    errors = {}
    if not target_user_id:
        errors["user_id"] = "user_id is required."
    if role not in TeamRole.values:
        errors["role"] = "Role must be either 'coach' or 'player'."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    target_user = get_object_or_404(User, pk=target_user_id)

    if not can_add_team_member(request.user, team, role):
        return JsonResponse(
            {"errors": {"authorization": "You cannot add that type of member to this team."}},
            status=403,
        )

    if not coach_may_add_user_to_team_roster(request.user, team, target_user, role):
        return JsonResponse(
            {
                "errors": {
                    "authorization": (
                        "Coaches may only add player accounts to the roster. "
                        "Users assigned as parent or director cannot be added by a coach."
                    )
                },
            },
            status=403,
        )

    membership = TeamMembership.objects.add_member(
        user=target_user,
        team=team,
        role=role,
    )
    if role == TeamRole.PLAYER:
        ensure_monthly_fee_for_new_player(team, target_user)
    return JsonResponse(
        {
            "message": "Team member added successfully.",
            "team": _serialize_team(team),
            "member": _serialize_team_member(membership),
        },
        status=201,
    )


@csrf_exempt
@login_required
@require_POST
def invite_team_member(request, team_id):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    invited_email = (payload.get("email") or "").strip().lower()
    role = (payload.get("role") or TeamRole.PLAYER).strip() or TeamRole.PLAYER

    errors = {}
    if not invited_email:
        errors["email"] = "Email is required."
    else:
        try:
            EmailValidator()(invited_email)
        except ValidationError:
            errors["email"] = "Enter a valid email address."
    if role not in TeamRole.values:
        errors["role"] = "Role must be either 'coach' or 'player'."
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    if not can_add_team_member(request.user, team, role):
        return JsonResponse(
            {"errors": {"authorization": "You cannot invite that type of member to this team."}},
            status=403,
        )

    existing_user = User.objects.filter(email=invited_email).first()
    if existing_user is not None:
        if TeamMembership.objects.active().filter(team=team, user=existing_user).exists():
            return JsonResponse(
                {"errors": {"email": "This user is already an active member of this team."}},
                status=400,
            )
        if not coach_may_add_user_to_team_roster(request.user, team, existing_user, role):
            return JsonResponse(
                {
                    "errors": {
                        "authorization": (
                            "Coaches may only invite player accounts; parent or director accounts cannot be invited by a coach."
                        )
                    }
                },
                status=403,
            )

    TeamInvitation.objects.filter(
        team=team,
        invited_email=invited_email,
        status=TeamInvitationStatus.PENDING,
    ).update(
        status=TeamInvitationStatus.EXPIRED,
        responded_at=timezone.now(),
    )
    invitation = TeamInvitation.objects.create(
        team=team,
        invited_email=invited_email,
        role=role,
        invited_by=request.user,
    )

    _send_team_invitation_email(
        invited_email=invited_email,
        team_name=team.name,
        club_name=team.club.name,
        code=invitation.code,
    )
    return JsonResponse(
        {
            "message": "Invitation sent successfully.",
            "invitation": _serialize_team_invitation(invitation),
        },
        status=201,
    )


@require_GET
def invitation_detail(request, code):
    invite = TeamInvitation.objects.select_related("team__club").filter(code=code).first()
    if invite is None:
        return JsonResponse({"errors": {"invitation": "Invitation not found."}}, status=404)

    invite = _expire_invitation_if_needed(invite)

    viewer_email = ""
    viewer_is_authenticated = False
    authorization_header = request.headers.get("Authorization", "").strip()
    scheme, _, token = authorization_header.partition(" ")
    if scheme == "Bearer" and token:
        try:
            auth_payload = verify_auth_token(token)
            authed_user = User.objects.filter(
                pk=auth_payload.get("user_id"),
                email=auth_payload.get("email"),
                is_active=True,
            ).first()
            if authed_user is not None:
                viewer_is_authenticated = True
                viewer_email = (authed_user.email or "").strip().lower()
        except (SignatureExpired, BadSignature):
            viewer_is_authenticated = False
            viewer_email = ""

    return JsonResponse(
        {
            "invitation": _serialize_team_invitation(invite),
            "requires_login": True,
            "viewer_is_authenticated": viewer_is_authenticated,
            "viewer_email_matches_invite": bool(
                viewer_email and viewer_email == (invite.invited_email or "").strip().lower()
            ),
        }
    )


@csrf_exempt
@login_required
@require_POST
def respond_team_invitation(request, code):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    action = (payload.get("action") or "").strip().lower()
    if action not in ("accept", "decline"):
        return JsonResponse({"errors": {"action": "Action must be 'accept' or 'decline'."}}, status=400)

    invite = TeamInvitation.objects.select_related("team__club").filter(code=code).first()
    if invite is None:
        return JsonResponse({"errors": {"invitation": "Invitation not found."}}, status=404)

    invite = _expire_invitation_if_needed(invite)
    if invite.status != TeamInvitationStatus.PENDING:
        return JsonResponse(
            {"errors": {"invitation": f"This invitation is already {invite.status}."}},
            status=400,
        )

    viewer_email = (request.user.email or "").strip().lower()
    if viewer_email != (invite.invited_email or "").strip().lower():
        return JsonResponse(
            {"errors": {"authorization": "This invitation belongs to a different email address."}},
            status=403,
        )

    if action == "decline":
        invite.status = TeamInvitationStatus.DECLINED
        invite.responded_at = timezone.now()
        invite.save(update_fields=["status", "responded_at"])
        return JsonResponse(
            {
                "message": "Invitation declined.",
                "invitation": _serialize_team_invitation(invite),
            }
        )

    TeamMembership.objects.add_member(
        user=request.user,
        team=invite.team,
        role=invite.role,
    )
    if invite.role == TeamRole.PLAYER:
        ensure_monthly_fee_for_new_player(invite.team, request.user)
    invite.status = TeamInvitationStatus.ACCEPTED
    invite.responded_at = timezone.now()
    invite.save(update_fields=["status", "responded_at"])
    return JsonResponse(
        {
            "message": "Invitation accepted. You are now a team member.",
            "invitation": _serialize_team_invitation(invite),
            "team": _serialize_team(invite.team),
        }
    )


@csrf_exempt
@login_required
@require_POST
def set_team_captain(request, team_id, player_id):
    team = get_object_or_404(Team, pk=team_id)
    if not can_manage_team(request.user, team):
        return JsonResponse(
            {"errors": {"authorization": "You cannot assign captains for this team."}},
            status=403,
        )

    membership = TeamMembership.objects.active().filter(
        user_id=player_id,
        team=team,
        role=TeamRole.PLAYER,
    ).select_related("user").first()
    if membership is None:
        return JsonResponse(
            {"errors": {"membership": "No active player membership was found for this user."}},
            status=404,
        )

    membership.is_captain = True
    membership.save(update_fields=["is_captain"])
    return JsonResponse(
        {
            "message": "Player set as captain successfully.",
            "team": _serialize_team(team),
            "member": _serialize_team_member(membership),
        }
    )


@csrf_exempt
@login_required
@require_http_methods(["DELETE"])
def remove_team_captain(request, team_id, player_id):
    team = get_object_or_404(Team, pk=team_id)
    if not can_manage_team(request.user, team):
        return JsonResponse(
            {"errors": {"authorization": "You cannot remove captains for this team."}},
            status=403,
        )

    membership = TeamMembership.objects.active().filter(
        user_id=player_id,
        team=team,
        role=TeamRole.PLAYER,
    ).select_related("user").first()
    if membership is None:
        return JsonResponse(
            {"errors": {"membership": "No active player membership was found for this user."}},
            status=404,
        )

    membership.is_captain = False
    membership.save(update_fields=["is_captain"])
    return JsonResponse(
        {
            "message": "Captain removed successfully.",
            "team": _serialize_team(team),
            "member": _serialize_team_member(membership),
        }
    )


@csrf_exempt
@login_required
@require_http_methods(["DELETE"])
def remove_team_member(request, team_id, target_user_id):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    team = get_object_or_404(Team, pk=team_id)
    target_user = get_object_or_404(User, pk=target_user_id)
    membership = TeamMembership.objects.active().filter(
        user=target_user,
        team=team,
    ).first()

    if membership is None:
        return JsonResponse(
            {"errors": {"membership": "No active team membership was found for this user."}},
            status=404,
        )

    if not can_manage_team_member(request.user, target_user, team):
        return JsonResponse(
            {"errors": {"authorization": "You cannot remove this team member."}},
            status=403,
        )

    TeamMembership.objects.deactivate(membership)
    return JsonResponse(
        {
            "message": "Team membership removed successfully.",
            "removed": {
                "user_id": target_user.id,
                "team_id": team.id,
                "membership": {
                    "role": membership.role,
                    "is_captain": membership.is_captain,
                    "is_active": membership.is_active,
                    "left_at": (
                        membership.left_at.isoformat() if membership.left_at else None
                    ),
                },
            },
        }
    )


@csrf_exempt
@login_required
@require_POST
def add_parent_association(request, player_id):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    player = get_object_or_404(User, pk=player_id)
    if not can_add_parent_association(request.user, player):
        return JsonResponse(
            {"errors": {"authorization": "You cannot link a parent to this player."}},
            status=403,
        )

    parent_id = payload.get("parent_id")
    if not parent_id:
        return JsonResponse({"errors": {"parent_id": "parent_id is required."}}, status=400)

    parent = get_object_or_404(User, pk=parent_id)
    if parent == player:
        return JsonResponse(
            {"errors": {"parent_id": "A user cannot be linked as their own parent."}},
            status=400,
        )

    coach_or_director_adds_other_parent = can_manage_player(request.user, player) and request.user.id != parent.id
    approval = (
        ParentLinkApprovalStatus.APPROVED
        if coach_or_director_adds_other_parent
        else ParentLinkApprovalStatus.PENDING
    )
    relation, created = ParentPlayerRelation.objects.link(
        parent=parent,
        player=player,
        is_legal_guardian=bool(payload.get("is_legal_guardian", False)),
        approval_status=approval,
    )

    if approval == ParentLinkApprovalStatus.PENDING:
        msg = (
            "Link request submitted. A club director must approve it before this parent can access the "
            "player's payments."
            if created
            else "Parent association updated; approval is still pending."
        )
    else:
        msg = "Parent linked successfully." if created else "Parent association saved successfully."

    return JsonResponse(
        {
            "message": msg,
            "relation": _serialize_parent_relation(relation),
        },
        status=201 if created else 200,
    )


@csrf_exempt
@login_required
@require_http_methods(["DELETE"])
def remove_parent_association(request, player_id, parent_id):
    player = get_object_or_404(User, pk=player_id)
    parent = get_object_or_404(User, pk=parent_id)
    relation = ParentPlayerRelation.objects.active().filter(
        parent=parent,
        player=player,
    ).first()

    if relation is None:
        return JsonResponse(
            {"errors": {"relation": "No active parent association was found."}},
            status=404,
        )

    if not can_remove_parent_association(request.user, player):
        return JsonResponse(
            {"errors": {"authorization": "You cannot remove this parent association."}},
            status=403,
        )

    ParentPlayerRelation.objects.deactivate(relation)
    return JsonResponse(
        {
            "message": "Parent association removed successfully.",
            "relation": _serialize_parent_relation(relation),
        }
    )


@csrf_exempt
@login_required
@require_http_methods(["GET", "PATCH"])
def manage_player_parent_access(request, player_id):
    player = get_object_or_404(User, pk=player_id)
    if not can_parent_manage_player_access(request.user, player):
        message = "You cannot manage parent-controlled access for this player."
        if is_user_adult(player):
            message = "Parent-managed access is only available for players under 18."
        return JsonResponse({"errors": {"authorization": message}}, status=403)

    policy = PlayerAccessPolicy.objects.get_or_create_for_player(player=player)

    if request.method == "GET":
        return JsonResponse(
            {
                "player": _serialize_basic_user(player),
                "policy": _serialize_player_access_policy(policy),
            }
        )

    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    field_mapping = {
        "is_parent_managed": "is_parent_managed",
        "can_self_confirm_attendance": "can_self_confirm_attendance",
        "can_self_make_payments": "can_self_make_payments",
        "can_self_submit_absence_reasons": "can_self_submit_absence_reasons",
        "can_self_approve_schedule_confirmations": (
            "can_self_approve_schedule_confirmations"
        ),
        "can_self_update_emergency_contact": "can_self_update_emergency_contact",
    }

    updated_fields = []
    for payload_key, model_field in field_mapping.items():
        if payload_key in payload:
            setattr(policy, model_field, bool(payload[payload_key]))
            updated_fields.append(model_field)

    if not updated_fields:
        return JsonResponse(
            {
                "errors": {
                    "payload": "No supported parent-managed access fields were provided."
                }
            },
            status=400,
        )

    policy.save(update_fields=updated_fields + ["updated_at"])
    return JsonResponse(
        {
            "message": "Parent-managed access updated successfully.",
            "player": _serialize_basic_user(player),
            "policy": _serialize_player_access_policy(policy),
        }
    )


@csrf_exempt
@login_required
@require_POST
def create_club(request):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    name = (payload.get("name") or "").strip()
    short_name = (payload.get("short_name") or "").strip()
    contact_email = (payload.get("contact_email") or "").strip().lower()
    contact_phone = (payload.get("contact_phone") or "").strip()
    country = (payload.get("country") or "").strip()
    city = (payload.get("city") or "").strip()
    address = (payload.get("address") or "").strip()
    founded_year_raw = payload.get("founded_year")
    errors = {}

    required_fields = {
        "name": (name, "Club name is required."),
        "short_name": (short_name, "Short name is required."),
        "contact_email": (contact_email, "Contact email is required."),
        "contact_phone": (contact_phone, "Contact phone is required."),
        "country": (country, "Country is required."),
        "city": (city, "City is required."),
        "address": (address, "Address is required."),
    }

    for field_name, (value, message) in required_fields.items():
        if not value:
            errors[field_name] = message

    founded_year = None
    if founded_year_raw in (None, ""):
        errors["founded_year"] = "Founded year is required."
    else:
        try:
            founded_year = int(founded_year_raw)
        except (TypeError, ValueError):
            errors["founded_year"] = "Founded year must be a valid year."
        else:
            current_year = date.today().year
            if founded_year < 1800 or founded_year > current_year:
                errors["founded_year"] = (
                    f"Founded year must be between 1800 and {current_year}."
                )

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    if Club.objects.filter(name=name).exists():
        return JsonResponse(
            {"errors": {"name": "A club with this name already exists."}},
            status=400,
        )

    club_data = {
        "short_name": short_name,
        "description": payload.get("description") or "",
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "website": (payload.get("website") or "").strip(),
        "country": country,
        "city": city,
        "address": address,
        "founded_year": founded_year,
    }

    try:
        club = Club.objects.create_club(
            name=name,
            director=request.user,
            **club_data,
        )
    except IntegrityError:
        return JsonResponse(
            {"errors": {"name": "A club with this name already exists."}},
            status=400,
        )

    return JsonResponse(
        {
            "message": "Club created successfully.",
            "club": {
                "id": club.id,
                "name": club.name,
                "short_name": club.short_name,
                "description": club.description,
                "contact_email": club.contact_email,
                "contact_phone": club.contact_phone,
                "website": club.website,
                "country": club.country,
                "city": club.city,
                "address": club.address,
                "founded_year": club.founded_year,
            },
            "membership": {
                "role": "club_director",
                "user_id": request.user.id,
            },
        },
        status=201,
    )


@csrf_exempt
@login_required
@require_POST
def create_team(request, club_id):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    club = get_object_or_404(Club, pk=club_id)
    if not _user_is_director_of_club(request.user, club):
        return JsonResponse(
            {"errors": {"authorization": "Only the club director can create teams for this club."}},
            status=403,
        )

    name = (payload.get("name") or "").strip()
    errors = {}

    if not name:
        errors["name"] = "Team name is required."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    team_data = {
        "short_name": (payload.get("short_name") or "").strip(),
        "description": payload.get("description") or "",
        "season": (payload.get("season") or "").strip(),
        "age_group": (payload.get("age_group") or "").strip(),
        "gender": (payload.get("gender") or "").strip(),
        "status": (payload.get("status") or Team.Status.ACTIVE).strip() or Team.Status.ACTIVE,
        "home_venue": (payload.get("home_venue") or "").strip(),
        "notes": payload.get("notes") or "",
    }

    try:
        team = Team.objects.create_team(
            club=club,
            name=name,
            **team_data,
        )
    except IntegrityError:
        return JsonResponse(
            {"errors": {"name": "A team with this name already exists in this club."}},
            status=400,
        )

    return JsonResponse(
        {
            "message": "Team created successfully.",
            "team": {
                "id": team.id,
                "club_id": club.id,
                "name": team.name,
                "short_name": team.short_name,
                "description": team.description,
                "season": team.season,
                "age_group": team.age_group,
                "gender": team.gender,
                "status": team.status,
                "home_venue": team.home_venue,
                "notes": team.notes,
            },
        },
        status=201,
    )


@csrf_exempt
@login_required
@require_http_methods(["DELETE"])
def delete_team(request, team_id):
    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    if not _user_is_director_of_club(request.user, team.club):
        return JsonResponse(
            {"errors": {"authorization": "Only club directors can delete teams for this club."}},
            status=403,
        )

    memberships = list(
        TeamMembership.objects.active().filter(team=team).select_related("user")
    )
    recipients = []
    seen_user_ids = set()
    for membership in memberships:
        if membership.user_id not in seen_user_ids:
            seen_user_ids.add(membership.user_id)
            recipients.append(membership.user)

    team_name = team.name
    club = team.club
    with transaction.atomic():
        for membership in memberships:
            TeamMembership.objects.deactivate(membership)
        team.delete()

    for recipient in recipients:
        _send_team_membership_removed_email(
            recipient=recipient,
            team_name=team_name,
            club_name=club.name,
            team_id=team_id,
        )

    return JsonResponse(
        {
            "message": "Team deleted successfully.",
            "deleted_team_id": team_id,
            "deleted_team_name": team_name,
            "memberships_removed_count": len(memberships),
            "notified_members_count": len(recipients),
        }
    )


@csrf_exempt
@login_required
@require_http_methods(["DELETE"])
def delete_club(request, club_id):
    club = get_object_or_404(Club, pk=club_id)
    if not _user_is_director_of_club(request.user, club):
        return JsonResponse(
            {"errors": {"authorization": "Only club directors can delete this club."}},
            status=403,
        )

    team_memberships = list(
        TeamMembership.objects.active()
        .filter(team__club=club)
        .select_related("user")
    )
    club_memberships = list(
        ClubMembership.objects.active()
        .filter(club=club)
        .select_related("user")
    )

    recipients = []
    seen_user_ids = set()
    for membership in team_memberships + club_memberships:
        if membership.user_id not in seen_user_ids:
            seen_user_ids.add(membership.user_id)
            recipients.append(membership.user)

    club_name = club.name
    with transaction.atomic():
        for membership in team_memberships:
            TeamMembership.objects.deactivate(membership)
        for membership in club_memberships:
            ClubMembership.objects.deactivate(membership)
        club.delete()

    for recipient in recipients:
        _send_club_membership_removed_email(
            recipient=recipient,
            club_name=club_name,
            club_id=club_id,
        )

    return JsonResponse(
        {
            "message": "Club deleted successfully.",
            "deleted_club_id": club_id,
            "deleted_club_name": club_name,
            "team_memberships_removed_count": len(team_memberships),
            "club_memberships_removed_count": len(club_memberships),
            "notified_members_count": len(recipients),
        }
    )


@csrf_exempt
@login_required
@require_http_methods(["PATCH"])
def update_team_details(request, team_id):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    team = get_object_or_404(Team, pk=team_id)
    if not can_manage_team(request.user, team):
        return JsonResponse(
            {"errors": {"authorization": "You cannot modify this team."}},
            status=403,
        )

    updated_fields = []
    updatable_fields = {
        "name": lambda value: (value or "").strip(),
        "short_name": lambda value: (value or "").strip(),
        "description": lambda value: value or "",
        "season": lambda value: (value or "").strip(),
        "age_group": lambda value: (value or "").strip(),
        "gender": lambda value: (value or "").strip(),
        "status": lambda value: (value or "").strip(),
        "home_venue": lambda value: (value or "").strip(),
        "notes": lambda value: value or "",
    }

    for field_name, transform in updatable_fields.items():
        if field_name in payload:
            setattr(team, field_name, transform(payload[field_name]))
            updated_fields.append(field_name)

    if "name" in updated_fields and not team.name:
        return JsonResponse({"errors": {"name": "Team name cannot be empty."}}, status=400)

    if not updated_fields:
        return JsonResponse(
            {"errors": {"payload": "No supported team fields were provided."}},
            status=400,
        )

    try:
        team.save(update_fields=updated_fields + ["updated_at"])
    except IntegrityError:
        return JsonResponse(
            {"errors": {"name": "A team with this name already exists in this club."}},
            status=400,
        )

    return JsonResponse(
        {
            "message": "Team details updated successfully.",
            "team": {
                "id": team.id,
                "club_id": team.club_id,
                "name": team.name,
                "short_name": team.short_name,
                "description": team.description,
                "season": team.season,
                "age_group": team.age_group,
                "gender": team.gender,
                "status": team.status,
                "home_venue": team.home_venue,
                "notes": team.notes,
            },
        }
    )


@csrf_exempt
@login_required
@require_http_methods(["PATCH"])
# Team-related data handled here:
# - Any authenticated user can edit their own emergency contact
# - Parents can edit their child's emergency contact for that team
# - Coaches and club directors can edit player profile fields for that team
def update_team_member_data(request, team_id, target_user_id):
    payload = _parse_json_request(request)
    if payload is None:
        return JsonResponse({"errors": {"body": "Invalid JSON."}}, status=400)

    team = get_object_or_404(Team, pk=team_id)
    target_user = get_object_or_404(User, pk=target_user_id)
    updated = {}
    membership = TeamMembership.objects.filter(
        user=target_user,
        team=team,
        is_active=True,
    ).first()
    is_self_edit = request.user == target_user
    is_parent_edit = is_parent_of_player_on_team(request.user, target_user, team)
    is_staff_team_edit = can_manage_team_member(request.user, target_user, team)

    if is_self_edit:
        if not can_view_team(request.user, team):
            return JsonResponse(
                {"errors": {"authorization": "You cannot modify this team member."}},
                status=403,
            )

        if "emergency_contact" in payload:
            if membership and membership.role == TeamRole.PLAYER:
                if not can_player_update_own_emergency_contact(request.user):
                    return JsonResponse(
                        {
                            "errors": {
                                "authorization": (
                                    "Your parent-managed settings do not allow you to update "
                                    "your emergency contact."
                                )
                            }
                        },
                        status=403,
                    )

            target_user.emergency_contact = (payload["emergency_contact"] or "").strip()
            target_user.save(update_fields=["emergency_contact"])
            updated["user"] = {
                "emergency_contact": target_user.emergency_contact,
            }

    elif is_parent_edit:
        if "emergency_contact" in payload:
            target_user.emergency_contact = (payload["emergency_contact"] or "").strip()
            target_user.save(update_fields=["emergency_contact"])
            updated["user"] = {
                "emergency_contact": target_user.emergency_contact,
            }

    elif is_staff_team_edit:
        if membership is not None and membership.role == TeamRole.PLAYER:
            profile, _ = PlayerProfile.objects.get_or_create(user=target_user)
            profile_updated_fields = []

            if "jersey_number" in payload:
                profile.jersey_number = payload["jersey_number"]
                profile_updated_fields.append("jersey_number")
            if "primary_position" in payload:
                profile.primary_position = (payload["primary_position"] or "").strip()
                profile_updated_fields.append("primary_position")
            if "notes" in payload:
                profile.notes = payload["notes"] or ""
                profile_updated_fields.append("notes")

            if profile_updated_fields:
                profile.save(update_fields=profile_updated_fields)
                updated["player_profile"] = {
                    "jersey_number": profile.jersey_number,
                    "primary_position": profile.primary_position,
                    "notes": profile.notes,
                }

    else:
        return JsonResponse(
            {"errors": {"authorization": "You cannot modify this team member."}},
            status=403,
        )

    if not updated:
        return JsonResponse(
            {
                "errors": {
                    "payload": "No supported team-based fields were provided for this user."
                }
            },
            status=400,
        )

    return JsonResponse(
        {
            "message": "Team-based data updated successfully.",
            "team_id": team.id,
            "target_user_id": target_user.id,
            "updated": updated,
        }
    )
