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
        "email",
        "first_name",
        "last_name",
        "date_of_birth",
        "is_staff",
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "date_of_birth")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "date_of_birth", "password1", "password2"),
            },
        ),
    )
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)


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
    search_fields = ("user__email", "user__first_name", "user__last_name", "club__name", "role")
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
    search_fields = ("user__email", "user__first_name", "user__last_name", "team__name", "role")
    list_filter = ("role", "is_captain", "is_active", "team__club")


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "jersey_number", "primary_position")
    search_fields = ("user__email", "user__first_name", "user__last_name", "primary_position")


@admin.register(ParentPlayerRelation)
class ParentPlayerRelationAdmin(admin.ModelAdmin):
    list_display = ("parent", "player")
    search_fields = (
        "parent__email",
        "parent__first_name",
        "parent__last_name",
        "player__email",
        "player__first_name",
        "player__last_name",
    )
