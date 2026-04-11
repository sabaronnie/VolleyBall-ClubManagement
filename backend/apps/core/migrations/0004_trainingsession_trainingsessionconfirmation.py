from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_teamscheduleentry"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TrainingSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                (
                    "session_type",
                    models.CharField(
                        choices=[("training", "Training"), ("match", "Match")],
                        default="training",
                        max_length=20,
                    ),
                ),
                ("scheduled_date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("location", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("scheduled", "Scheduled"), ("cancelled", "Cancelled")],
                        default="scheduled",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_training_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="training_sessions",
                        to="core.team",
                    ),
                ),
            ],
            options={
                "ordering": ["scheduled_date", "start_time", "title"],
            },
        ),
        migrations.CreateModel(
            name="TrainingSessionConfirmation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("confirmed_at", models.DateTimeField(auto_now=True)),
                (
                    "confirmed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="submitted_training_session_confirmations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="training_session_confirmations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "training_session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="confirmations",
                        to="core.trainingsession",
                    ),
                ),
            ],
            options={
                "ordering": ["player__first_name", "player__last_name", "player__email"],
            },
        ),
        migrations.AddConstraint(
            model_name="trainingsessionconfirmation",
            constraint=models.UniqueConstraint(
                fields=("training_session", "player"),
                name="unique_training_session_confirmation_per_player",
            ),
        ),
    ]
