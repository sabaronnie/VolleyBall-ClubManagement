from django.urls import path

from .views import (
    create_club,
    create_team,
    login,
    me,
    register,
    update_team_details,
    update_team_member_data,
)

app_name = "core"

urlpatterns = [
    path("auth/login/", login, name="login"),
    path("auth/me/", me, name="me"),
    path("clubs/create/", create_club, name="create-club"),
    path("clubs/<int:club_id>/teams/create/", create_team, name="create-team"),
    path("register/", register, name="register"),
    path("teams/<int:team_id>/update/", update_team_details, name="update-team-details"),
    path(
        "teams/<int:team_id>/members/<int:target_user_id>/team-data/",
        update_team_member_data,
        name="update-team-member-data",
    ),
]
