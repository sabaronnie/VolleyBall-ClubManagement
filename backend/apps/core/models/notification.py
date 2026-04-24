from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Category(models.TextChoices):
        SESSION = "session", "Session"
        SCHEDULE = "schedule", "Schedule"
        MANUAL = "manual", "Manual"
        MATCH_REQUEST = "match_request", "Match request"
        ATTENDANCE_INCOMPLETE = "attendance_incomplete", "Attendance incomplete"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_notifications",
    )
    team = models.ForeignKey(
        "core.Team",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    training_session = models.ForeignKey(
        "core.TrainingSession",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="incomplete_attendance_notifications",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(
        max_length=32,
        choices=Category.choices,
        default=Category.MANUAL,
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "training_session", "category"],
                condition=models.Q(
                    category="attendance_incomplete",
                    training_session__isnull=False,
                ),
                name="core_notification_unique_attendance_incomplete",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.recipient} - {self.title}"
