from django.urls import path

from .views import (
    add_parent_association,
    add_team_member,
    clear_training_session,
    create_club,
    create_team,
    confirm_training_session,
    login,
    mark_notifications_read,
    manage_player_parent_access,
    manage_training_session,
    me,
    notifications,
    remove_parent_association,
    remove_team_captain,
    remove_team_member,
    register,
    send_team_notification,
    set_team_captain,
    team_schedule,
    team_training_sessions,
    update_team_details,
    update_team_member_data,
    view_team_members,
)

app_name = "core"

urlpatterns = [
    path("auth/login/", login, name="login"),
    path("auth/me/", me, name="me"),
    path("notifications/", notifications, name="notifications"),
    path("notifications/read/", mark_notifications_read, name="mark-notifications-read"),
    path("notifications/send/", send_team_notification, name="send-team-notification"),
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
    path("teams/<int:team_id>/schedule/", team_schedule, name="team-schedule"),
    path(
        "teams/<int:team_id>/training-sessions/",
        team_training_sessions,
        name="team-training-sessions",
    ),
    path(
        "training-sessions/<int:session_id>/",
        manage_training_session,
        name="manage-training-session",
    ),
    path(
        "training-sessions/<int:session_id>/confirm/",
        confirm_training_session,
        name="confirm-training-session",
    ),
    path(
        "training-sessions/<int:session_id>/clear/",
        clear_training_session,
        name="clear-training-session",
    ),
    path("teams/<int:team_id>/members/add/", add_team_member, name="add-team-member"),
    path(
        "teams/<int:team_id>/captains/<int:player_id>/",
        set_team_captain,
        name="set-team-captain",
    ),
    path(
        "teams/<int:team_id>/captains/<int:player_id>/remove/",
        remove_team_captain,
        name="remove-team-captain",
    ),
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
