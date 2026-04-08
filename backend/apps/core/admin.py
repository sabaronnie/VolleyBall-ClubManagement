from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Club, ClubMembership, ParentPlayerRelation, Team, TeamMembership, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
    )
    search_fields = ("username", "email", "first_name", "last_name")


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "club")
    search_fields = ("name", "club__name")
    list_filter = ("club",)


@admin.register(ClubMembership)
class ClubMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "club", "role")
    search_fields = ("user__username", "club__name", "role")
    list_filter = ("role", "club")


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "team", "role")
    search_fields = ("user__username", "team__name", "role")
    list_filter = ("role", "team__club")


@admin.register(ParentPlayerRelation)
class ParentPlayerRelationAdmin(admin.ModelAdmin):
    list_display = ("parent", "player")
    search_fields = ("parent__username", "player__username")
