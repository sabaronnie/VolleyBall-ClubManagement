from django.utils import timezone

from .models import (
    AssignedAccountRole,
    ClubMembership,
    ClubRole,
    ParentPlayerRelation,
    PlayerAccessPolicy,
    TeamMembership,
    TeamRole,
)


def is_staff_user(user) -> bool:
    return bool(user and user.is_authenticated and user.is_staff)


def is_user_adult(user) -> bool:
    if not user or not user.date_of_birth:
        return False

    today = timezone.localdate()
    years = today.year - user.date_of_birth.year
    if (today.month, today.day) < (user.date_of_birth.month, user.date_of_birth.day):
        years -= 1
    return years >= 18


def is_club_director(user, club) -> bool:
    if is_staff_user(user):
        return True

    return ClubMembership.objects.active().filter(
        user=user,
        club=club,
        role=ClubRole.CLUB_DIRECTOR,
    ).exists()


def is_any_club_director(user) -> bool:
    if is_staff_user(user):
        return True

    return ClubMembership.objects.active().filter(
        user=user,
        role=ClubRole.CLUB_DIRECTOR,
    ).exists()


def is_team_coach(user, team) -> bool:
    if is_staff_user(user):
        return True

    return TeamMembership.objects.active().filter(
        user=user,
        team=team,
        role=TeamRole.COACH,
    ).exists()


def is_team_player(user, team) -> bool:
    if is_staff_user(user):
        return True

    return TeamMembership.objects.active().filter(
        user=user,
        team=team,
        role=TeamRole.PLAYER,
    ).exists()


def is_parent_of_player(user, player_user) -> bool:
    if is_staff_user(user):
        return True

    return ParentPlayerRelation.objects.approved().filter(
        parent=user,
        player=player_user,
    ).exists()


def is_parent_of_team_player(user, team) -> bool:
    if is_staff_user(user):
        return True

    return ParentPlayerRelation.objects.approved().filter(
        parent=user,
        player__team_memberships__team=team,
        player__team_memberships__role=TeamRole.PLAYER,
        player__team_memberships__is_active=True,
    ).exists()


def is_parent_of_player_on_team(user, player_user, team) -> bool:
    if is_staff_user(user):
        return True

    return ParentPlayerRelation.objects.approved().filter(
        parent=user,
        player=player_user,
        player__team_memberships__team=team,
        player__team_memberships__role=TeamRole.PLAYER,
        player__team_memberships__is_active=True,
    ).exists()


def can_view_club(user, club) -> bool:
    return is_club_director(user, club)


def can_manage_club(user, club) -> bool:
    return is_club_director(user, club)


def is_club_coach(user, club) -> bool:
    """True if the user is an active coach on any team in this club (not necessarily club director)."""
    return TeamMembership.objects.active().filter(
        user=user,
        team__club=club,
        role=TeamRole.COACH,
    ).exists()


def can_view_team(user, team) -> bool:
    return any(
        [
            is_club_director(user, team.club),
            is_team_coach(user, team),
            is_team_player(user, team),
            is_parent_of_team_player(user, team),
        ]
    )


def can_manage_team(user, team) -> bool:
    return any(
        [
            is_club_director(user, team.club),
            is_team_coach(user, team),
        ]
    )


def can_add_team_member(actor, team, role) -> bool:
    if is_staff_user(actor):
        return True

    if is_club_director(actor, team.club):
        return role in [TeamRole.COACH, TeamRole.PLAYER]

    if is_team_coach(actor, team):
        return role == TeamRole.PLAYER

    return False


def coach_may_add_user_to_team_roster(actor, team, target_user, team_role: str) -> bool:
    """Extra roster rule: coaches cannot add parent- or director-assigned users as players."""
    if is_staff_user(actor) or is_club_director(actor, team.club):
        return True
    if team_role != TeamRole.PLAYER:
        return False
    if not is_team_coach(actor, team):
        return True
    assigned = (getattr(target_user, "assigned_account_role", None) or "").strip()
    if assigned in (AssignedAccountRole.PARENT, AssignedAccountRole.DIRECTOR):
        return False
    return True


def can_view_player(user, player_user) -> bool:
    if is_staff_user(user):
        return True

    if user == player_user:
        return True

    if is_parent_of_player(user, player_user):
        return True

    return TeamMembership.objects.active().filter(
        user=user,
        team__memberships__user=player_user,
        team__memberships__role=TeamRole.PLAYER,
        team__memberships__is_active=True,
        role__in=[TeamRole.COACH, TeamRole.PLAYER],
    ).exists() or ClubMembership.objects.active().filter(
        user=user,
        club__teams__memberships__user=player_user,
        club__teams__memberships__role=TeamRole.PLAYER,
        club__teams__memberships__is_active=True,
        role=ClubRole.CLUB_DIRECTOR,
    ).exists()


def can_manage_player(user, player_user) -> bool:
    if is_staff_user(user):
        return True

    return TeamMembership.objects.active().filter(
        user=user,
        team__memberships__user=player_user,
        team__memberships__role=TeamRole.PLAYER,
        team__memberships__is_active=True,
        role=TeamRole.COACH,
    ).exists() or ClubMembership.objects.active().filter(
        user=user,
        club__teams__memberships__user=player_user,
        club__teams__memberships__role=TeamRole.PLAYER,
        club__teams__memberships__is_active=True,
        role=ClubRole.CLUB_DIRECTOR,
    ).exists()


def can_add_parent_association(actor, player_user) -> bool:
    if is_staff_user(actor):
        return True

    return actor == player_user or can_manage_player(actor, player_user)


def can_remove_parent_association(actor, player_user) -> bool:
    if is_staff_user(actor):
        return True

    if actor == player_user:
        return is_user_adult(player_user)

    return can_manage_player(actor, player_user)


def can_parent_manage_player_access(parent, player_user) -> bool:
    if is_staff_user(parent):
        return True

    if is_user_adult(player_user):
        return False

    return is_parent_of_player(parent, player_user)


def is_player_parent_managed(player_user) -> bool:
    if is_user_adult(player_user):
        return False

    if not ParentPlayerRelation.objects.approved().filter(player=player_user).exists():
        return False

    policy = PlayerAccessPolicy.objects.for_player(player_user).first()
    return bool(policy and policy.is_parent_managed)


def player_has_self_service_privilege(player_user, feature: str) -> bool:
    if is_user_adult(player_user):
        return True

    if not is_player_parent_managed(player_user):
        return True

    policy = PlayerAccessPolicy.objects.for_player(player_user).first()
    if policy is None:
        return True

    return policy.allows_player(feature)


def can_player_confirm_attendance(player_user) -> bool:
    return player_has_self_service_privilege(player_user, "confirm_attendance")


def can_player_make_payments(player_user) -> bool:
    return player_has_self_service_privilege(player_user, "make_payments")


def can_player_submit_absence_reasons(player_user) -> bool:
    return player_has_self_service_privilege(player_user, "submit_absence_reasons")


def can_player_approve_schedule_confirmations(player_user) -> bool:
    return player_has_self_service_privilege(player_user, "approve_schedule_confirmations")


def can_player_update_own_emergency_contact(player_user) -> bool:
    return player_has_self_service_privilege(player_user, "update_emergency_contact")


def can_manage_team_member(actor, target_user, team) -> bool:
    if is_staff_user(actor):
        return True

    if is_club_director(actor, team.club):
        return any(
            [
                is_team_coach(target_user, team),
                is_team_player(target_user, team),
            ]
        )

    if is_team_coach(actor, team):
        return any(
            [
                is_team_player(target_user, team),
            ]
        )

    return False
