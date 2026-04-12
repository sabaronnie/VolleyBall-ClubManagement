from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Club,
    ClubMembership,
    DirectorPaymentAuditLog,
    FeePaymentLedgerEntry,
    Notification,
    ParentPlayerRelation,
    PlayerAccessPolicy,
    PlayerFeeRecord,
    PlayerProfile,
    TeamScheduleEntry,
    TrainingSession,
    TrainingSessionConfirmation,
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
    list_display = ("name", "short_name", "city", "country", "contact_email", "default_monthly_player_fee")
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


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "title", "category", "team", "is_read", "created_at")
    search_fields = (
        "recipient__email",
        "recipient__first_name",
        "recipient__last_name",
        "title",
        "message",
        "team__name",
    )
    list_filter = ("category", "is_read", "team__club", "team")


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


@admin.register(TeamScheduleEntry)
class TeamScheduleEntryAdmin(admin.ModelAdmin):
    list_display = ("team", "activity_name", "weekday", "start_time", "end_time", "location", "created_by")
    search_fields = ("team__name", "team__club__name", "activity_name", "location", "created_by__email")
    list_filter = ("team__club", "team", "weekday")


@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "team",
        "session_type",
        "opponent",
        "match_type",
        "scheduled_date",
        "start_time",
        "end_time",
        "status",
        "created_by",
    )
    search_fields = (
        "title",
        "team__name",
        "team__club__name",
        "location",
        "opponent",
        "created_by__email",
    )
    list_filter = ("team__club", "team", "session_type", "status", "scheduled_date")


@admin.register(TrainingSessionConfirmation)
class TrainingSessionConfirmationAdmin(admin.ModelAdmin):
    list_display = ("training_session", "player", "confirmed_by", "confirmed_at")
    search_fields = (
        "training_session__title",
        "training_session__team__name",
        "player__email",
        "player__first_name",
        "player__last_name",
        "confirmed_by__email",
    )
    list_filter = ("training_session__team__club", "training_session__team", "training_session__scheduled_date")


@admin.register(PlayerFeeRecord)
class PlayerFeeRecordAdmin(admin.ModelAdmin):
    list_display = ("club", "player", "amount_due", "amount_paid", "due_date", "currency", "description")
    list_filter = ("club", "currency", "due_date")
    search_fields = ("player__email", "player__first_name", "player__last_name", "description")
    raw_id_fields = ("player", "team")


@admin.register(FeePaymentLedgerEntry)
class FeePaymentLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("fee_record", "amount", "recorded_at", "note")
    list_filter = ("recorded_at",)


@admin.register(DirectorPaymentAuditLog)
class DirectorPaymentAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "club", "actor", "action", "fee_record")
    list_filter = ("club", "action", "created_at")
    search_fields = ("detail", "actor__email")
