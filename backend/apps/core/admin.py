from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Club,
    ClubMembership,
    ParentPlayerRelation,
    PlayerProfile,
    Team,
    TeamMembership,
    User,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "date_of_birth",
        "first_name",
        "last_name",
        "is_staff",
    )
    fieldsets = UserAdmin.fieldsets + (
        ("Personal Info", {"fields": ("date_of_birth",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Personal Info", {"classes": ("wide",), "fields": ("email", "date_of_birth")}),
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
    list_display = ("user", "club", "role", "is_active", "joined_at", "left_at")
    search_fields = ("user__username", "club__name", "role")
    list_filter = ("role", "is_active", "club")


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "team",
        "role",
        "is_captain",
        "is_active",
        "joined_at",
        "left_at",
    )
    search_fields = ("user__username", "team__name", "role")
    list_filter = ("role", "is_captain", "is_active", "team__club")


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "jersey_number", "primary_position")
    search_fields = ("user__username", "user__email", "primary_position")


@admin.register(ParentPlayerRelation)
class ParentPlayerRelationAdmin(admin.ModelAdmin):
    list_display = ("parent", "player")
    search_fields = ("parent__username", "player__username")
