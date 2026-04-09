import json
from datetime import date

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST, require_http_methods

from .decorators import login_required
from .models import (
    Club,
    ClubMembership,
    ClubRole,
    ParentPlayerRelation,
    PlayerAccessPolicy,
    PlayerProfile,
    Team,
    TeamMembership,
    TeamRole,
)
from .permissions import (
    can_add_parent_association,
    can_manage_club,
    can_manage_team,
    can_manage_team_member,
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
    coached_teams = [
        _serialize_team(membership.team)
        for membership in TeamMembership.objects.active()
        .filter(user=request.user, role=TeamRole.COACH)
        .select_related("team__club")
    ]
    player_teams = [
        _serialize_team(membership.team)
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
            _serialize_team(membership.team)
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

    return JsonResponse(
        {
            "team": _serialize_team(team),
            "members": [_serialize_team_member(membership) for membership in memberships],
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
