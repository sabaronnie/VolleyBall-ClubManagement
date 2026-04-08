from django.urls import path

from .views import login, me, register, update_team_member_data

app_name = "core"

urlpatterns = [
    path("auth/login/", login, name="login"),
    path("auth/me/", me, name="me"),
    path("register/", register, name="register"),
    path(
        "teams/<int:team_id>/members/<int:target_user_id>/team-data/",
        update_team_member_data,
        name="update-team-member-data",
    ),
]
