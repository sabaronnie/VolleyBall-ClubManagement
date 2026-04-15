import apps.core.models.player_parent_invitation
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_team_invitation"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlayerParentInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invited_email", models.EmailField(max_length=254)),
                (
                    "code",
                    models.CharField(
                        default=apps.core.models.player_parent_invitation._generate_code,
                        max_length=128,
                        unique=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending_approval", "Pending approval"),
                            ("pending_parent_response", "Pending parent response"),
                            ("accepted", "Accepted"),
                            ("declined", "Declined"),
                            ("rejected", "Rejected"),
                            ("expired", "Expired"),
                        ],
                        default="pending_approval",
                        max_length=32,
                    ),
                ),
                ("director_approved_at", models.DateTimeField(blank=True, null=True)),
                ("coach_approved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("invited_at", models.DateTimeField(blank=True, null=True)),
                (
                    "expires_at",
                    models.DateTimeField(default=apps.core.models.player_parent_invitation._default_expiry),
                ),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "coach_approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_parent_invitations_as_coach",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "director_approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_parent_invitations_as_director",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "invited_parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="received_parent_invitations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parent_invitations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="requested_parent_invitations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="playerparentinvitation",
            index=models.Index(fields=["code"], name="core_ppi_code_idx"),
        ),
        migrations.AddIndex(
            model_name="playerparentinvitation",
            index=models.Index(fields=["player", "status"], name="core_ppi_player_status_idx"),
        ),
        migrations.AddIndex(
            model_name="playerparentinvitation",
            index=models.Index(fields=["invited_email", "status"], name="core_ppi_email_status_idx"),
        ),
    ]
