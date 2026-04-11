import json
from datetime import date, datetime, timedelta

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST, require_http_methods

from .decorators import login_required
from .models import (
    Club,
    ClubMembership,
    ClubRole,
    Notification,
    ParentPlayerRelation,
    PlayerAccessPolicy,
    PlayerProfile,
    Team,
    TeamMembership,
    TeamRole,
    TeamScheduleEntry,
    TrainingSession,
    TrainingSessionConfirmation,
)
from .permissions import (
    can_add_parent_association,
    can_add_team_member,
    can_manage_club,
    can_manage_team,
    can_manage_team_member,
    can_player_confirm_attendance,
    can_player_update_own_emergency_contact,
    can_parent_manage_player_access,
    can_remove_parent_association,
    can_view_team,
    is_parent_of_player_on_team,
    is_user_adult,
)
from .tokens import generate_auth_token


User = get_user_model()


def _parse_json_request(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _parse_date_of_birth(value):
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({"date_of_birth": "Use YYYY-MM-DD format."}) from exc


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
        "parent": _serialize_basic_user(relation.parent),
        "player_id": relation.player_id,
        "is_legal_guardian": relation.is_legal_guardian,
        "is_active": relation.is_active,
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
    return {
        "id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "category": notification.category,
        "team_name": notification.team.name if notification.team else None,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
    }


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
        ParentPlayerRelation.objects.active()
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


@csrf_exempt
@require_POST
def register(request):
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

    try:
        validate_password(password)
        date_of_birth = _parse_date_of_birth(payload.get("date_of_birth"))
    except ValidationError as exc:
        if hasattr(exc, "message_dict"):
            return JsonResponse({"errors": exc.message_dict}, status=400)
        messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return JsonResponse({"errors": {"password": messages}}, status=400)

    try:
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
        )
    except IntegrityError:
        return JsonResponse(
            {"errors": {"email": "An account with this email already exists."}},
            status=400,
        )

    return JsonResponse(
        {
            "message": "User registered successfully.",
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "date_of_birth": (
                    user.date_of_birth.isoformat() if user.date_of_birth else None
                ),
            },
        },
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

    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    token = generate_auth_token(user)
    return JsonResponse(
        {
            "message": "Authentication successful.",
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        }
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
            "can_manage_schedule": can_manage_team(request.user, membership.team),
            "can_manage_training": can_manage_team(request.user, membership.team),
        }
        for membership in TeamMembership.objects.active()
        .filter(user=request.user, role=TeamRole.PLAYER)
        .select_related("team__club")
    ]
    children = []
    parent_relations = ParentPlayerRelation.objects.active().filter(
        parent=request.user,
    ).select_related("player")

    for relation in parent_relations:
        child_teams = [
            {
                **_serialize_team_summary(membership.team),
                "can_manage_schedule": can_manage_team(request.user, membership.team),
                "can_manage_training": can_manage_team(request.user, membership.team),
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
            "owned_clubs": owned_clubs,
            "director_teams": director_teams,
            "coached_teams": coached_teams,
            "player_teams": player_teams,
            "children": children,
        }
    )


@login_required
@require_GET
def view_team_members(request, team_id):
    team = get_object_or_404(Team.objects.select_related("club"), pk=team_id)
    memberships = (
        TeamMembership.objects.active()
        .filter(team=team)
        .select_related("user")
        .order_by("role", "user__first_name", "user__last_name", "user__email")
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

    return JsonResponse(
        {
            "team": _serialize_team(team),
            "members": [_serialize_team_member(membership) for membership in memberships],
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

    return JsonResponse(
        {
            "message": "Attendance confirmed successfully.",
            "session": _serialize_training_session(session, request.user, team, player_memberships),
        }
    )


@login_required
@require_GET
def notifications(request):
    notification_items = list(
        Notification.objects.filter(recipient=request.user)
        .select_related("team")
    )
    unread_count = sum(1 for item in notification_items if not item.is_read)
    sent_items = []
    team_id = request.GET.get("team_id")

    if team_id:
        try:
            team = Team.objects.select_related("club").get(pk=team_id)
        except Team.DoesNotExist:
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

    membership = TeamMembership.objects.add_member(
        user=target_user,
        team=team,
        role=role,
    )
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

    relation, created = ParentPlayerRelation.objects.link(
        parent=parent,
        player=player,
        is_legal_guardian=bool(payload.get("is_legal_guardian", False)),
    )

    return JsonResponse(
        {
            "message": (
                "Parent linked successfully."
                if created
                else "Parent association saved successfully."
            ),
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
    errors = {}

    if not name:
        errors["name"] = "Club name is required."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    club_data = {
        "short_name": (payload.get("short_name") or "").strip(),
        "description": payload.get("description") or "",
        "contact_email": (payload.get("contact_email") or "").strip().lower(),
        "contact_phone": (payload.get("contact_phone") or "").strip(),
        "website": (payload.get("website") or "").strip(),
        "country": (payload.get("country") or "").strip(),
        "city": (payload.get("city") or "").strip(),
        "address": (payload.get("address") or "").strip(),
        "founded_year": payload.get("founded_year"),
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
    if not can_manage_club(request.user, club):
        return JsonResponse(
            {"errors": {"authorization": "You cannot create teams for this club."}},
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
