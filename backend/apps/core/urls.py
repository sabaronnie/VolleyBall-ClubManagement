from django.urls import path

from .views import (
    add_parent_association,
    create_club,
    create_team,
    login,
    manage_player_parent_access,
    me,
    remove_parent_association,
    remove_team_member,
    register,
    update_team_details,
    update_team_member_data,
    view_team_members,
)

app_name = "core"

urlpatterns = [
    path("auth/login/", login, name="login"),
    path("auth/me/", me, name="me"),
    path("clubs/create/", create_club, name="create-club"),
    path("clubs/<int:club_id>/teams/create/", create_team, name="create-team"),
    path("players/<int:player_id>/parents/", add_parent_association, name="add-parent-association"),
    path(
        "players/<int:player_id>/parents/<int:parent_id>/",
        remove_parent_association,
        name="remove-parent-association",
    ),
    path(
        "players/<int:player_id>/parent-management/",
        manage_player_parent_access,
        name="manage-player-parent-access",
    ),
    path("register/", register, name="register"),
    path("teams/<int:team_id>/members/", view_team_members, name="view-team-members"),
    path(
        "teams/<int:team_id>/members/<int:target_user_id>/remove/",
        remove_team_member,
        name="remove-team-member",
    ),
    path("teams/<int:team_id>/update/", update_team_details, name="update-team-details"),
    path(
        "teams/<int:team_id>/members/<int:target_user_id>/team-data/",
        update_team_member_data,
        name="update-team-member-data",
    ),
]
