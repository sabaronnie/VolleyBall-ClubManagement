from django.db import models


class ContactSubmission(models.Model):
    """Inbound marketing / support messages from the public Contact Us form."""

    class ContactRole(models.TextChoices):
        PLAYER = "player", "Player"
        PARENT = "parent", "Parent"
        COACH = "coach", "Coach"
        DIRECTOR = "director", "Director"
        OTHER = "other", "Other"

    name = models.CharField(max_length=200)
    email = models.EmailField()
    role = models.CharField(max_length=32, choices=ContactRole.choices)
    message = models.TextField()
    phone = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.email} ({self.get_role_display()}) @ {self.created_at:%Y-%m-%d}"
