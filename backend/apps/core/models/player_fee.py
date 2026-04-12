from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class PlayerFeeRecord(models.Model):
    """Per-player fee line item for a club (director-managed)."""

    club = models.ForeignKey(
        "core.Club",
        on_delete=models.CASCADE,
        related_name="player_fee_records",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="player_fee_records",
    )
    team = models.ForeignKey(
        "core.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="player_fee_records",
    )
    schedule = models.ForeignKey(
        "core.PaymentSchedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fee_records",
    )
    description = models.CharField(max_length=255, default="Club fee")
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="USD")
    due_date = models.DateField()
    billing_period_start = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="First day of the calendar month this recurring fee belongs to (if set).",
    )
    schedule_occurrence_key = models.CharField(
        max_length=128,
        blank=True,
        default="",
        db_index=True,
        help_text="Stable id for one row materialized from a payment schedule (due date + player + schedule).",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-due_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["club", "player", "team", "billing_period_start"],
                name="unique_player_team_billing_period_fee",
            ),
        ]

    def remaining(self) -> Decimal:
        return max(self.amount_due - self.amount_paid, Decimal("0.00"))

    def status(self) -> str:
        if self.remaining() <= 0:
            return "paid"
        if self.due_date < timezone.localdate():
            return "overdue"
        return "pending"

    def __str__(self) -> str:
        return f"{self.player.email} {self.club.name} {self.amount_due}"


class FeePaymentLedgerEntry(models.Model):
    """Each payment applied to a fee record (for accurate monthly collection totals)."""

    fee_record = models.ForeignKey(
        PlayerFeeRecord,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    recorded_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-recorded_at", "-id"]


class PaymentSchedule(models.Model):
    """A recurring (or one-time) payment plan created by a director."""

    class Frequency(models.TextChoices):
        ONCE = "once", "Once"
        HOURLY = "hourly", "Hourly"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    class Scope(models.TextChoices):
        CLUB = "club", "Entire club"
        TEAM = "team", "Specific team"
        PLAYER = "player", "Specific player"

    club = models.ForeignKey(
        "core.Club",
        on_delete=models.CASCADE,
        related_name="payment_schedules",
    )
    team = models.ForeignKey(
        "core.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_schedules",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="targeted_payment_schedules",
    )
    scope = models.CharField(max_length=10, choices=Scope.choices)
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    description = models.CharField(max_length=255)
    start_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_payment_schedules",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.description} ({self.frequency}) — {self.club.name}"


class DirectorPaymentAuditLog(models.Model):
    class Action(models.TextChoices):
        FEE_CREATED = "fee_created", "Fee created"
        PAYMENT_RECORDED = "payment_recorded", "Payment recorded"
        REMINDER_SENT = "reminder_sent", "Payment reminder sent"
        RECEIPT_SENT = "receipt_sent", "Receipt emailed"
        BULK_STATEMENTS_SENT = "bulk_statements_sent", "Bulk statements emailed"
        MONTHLY_FEES_MATERIALIZED = "monthly_fees_materialized", "Monthly fees materialized"

    club = models.ForeignKey(
        "core.Club",
        on_delete=models.CASCADE,
        related_name="payment_audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_audit_actions",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    detail = models.TextField(blank=True)
    fee_record = models.ForeignKey(
        PlayerFeeRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
