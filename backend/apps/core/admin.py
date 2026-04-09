from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Club,
    ClubMembership,
    ParentPlayerRelation,
    PlayerAccessPolicy,
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
        "emergency_contact",
        "is_staff",
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal Info",
            {"fields": ("first_name", "last_name", "date_of_birth", "emergency_contact")},
        ),
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
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "emergency_contact",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    search_fields = ("email", "first_name", "last_name", "emergency_contact")
    ordering = ("email",)


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "city", "country", "contact_email")
    search_fields = ("name", "short_name", "city", "country", "contact_email")
    list_filter = ("country", "city")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "club", "season", "age_group", "gender", "status")
    search_fields = ("name", "short_name", "club__name", "season", "age_group", "home_venue")
    list_filter = ("club", "status", "gender", "season", "age_group")


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
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "primary_position",
    )


@admin.register(ParentPlayerRelation)
class ParentPlayerRelationAdmin(admin.ModelAdmin):
    list_display = (
        "parent",
        "player",
        "is_legal_guardian",
        "is_active",
    )
    search_fields = (
        "parent__email",
        "parent__first_name",
        "parent__last_name",
        "player__email",
        "player__first_name",
        "player__last_name",
    )
    list_filter = ("is_legal_guardian", "is_active")


@admin.register(PlayerAccessPolicy)
class PlayerAccessPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "is_parent_managed",
        "can_self_confirm_attendance",
        "can_self_make_payments",
        "can_self_submit_absence_reasons",
        "can_self_approve_schedule_confirmations",
        "can_self_update_emergency_contact",
    )
    search_fields = (
        "player__email",
        "player__first_name",
        "player__last_name",
    )
    list_filter = (
        "is_parent_managed",
        "can_self_confirm_attendance",
        "can_self_make_payments",
        "can_self_submit_absence_reasons",
        "can_self_approve_schedule_confirmations",
        "can_self_update_emergency_contact",
    )
