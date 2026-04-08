from django.urls import path

from .views import login, me, register

app_name = "core"

urlpatterns = [
    path("auth/login/", login, name="login"),
    path("auth/me/", me, name="me"),
    path("register/", register, name="register"),
]
