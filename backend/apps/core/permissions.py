from .models import ClubMembership, ClubRole, ParentPlayerRelation, TeamMembership, TeamRole


def is_staff_user(user) -> bool:
    return bool(user and user.is_authenticated and user.is_staff)


def is_club_director(user, club) -> bool:
    if is_staff_user(user):
        return True

    return ClubMembership.objects.active().filter(
        user=user,
        club=club,
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

    return ParentPlayerRelation.objects.filter(
        parent=user,
        player=player_user,
    ).exists()


def is_parent_of_team_player(user, team) -> bool:
    if is_staff_user(user):
        return True

    return ParentPlayerRelation.objects.filter(
        parent=user,
        player__team_memberships__team=team,
        player__team_memberships__role=TeamRole.PLAYER,
        player__team_memberships__is_active=True,
    ).exists()


def can_view_club(user, club) -> bool:
    return is_club_director(user, club)


def can_manage_club(user, club) -> bool:
    return is_club_director(user, club)


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


def can_manage_team_member(actor, target_user, team) -> bool:
    if is_staff_user(actor):
        return True

    if is_club_director(actor, team.club):
        return any(
            [
                is_team_coach(target_user, team),
                is_team_player(target_user, team),
                is_parent_of_team_player(target_user, team),
            ]
        )

    if is_team_coach(actor, team):
        return any(
            [
                is_team_player(target_user, team),
                is_parent_of_team_player(target_user, team),
            ]
        )

    return False
