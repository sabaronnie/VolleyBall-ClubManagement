from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_match_player_stat"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="trainingsession",
            name="match_request_status",
            field=models.CharField(
                choices=[
                    ("none", "No approval needed"),
                    ("pending", "Pending opponent approval"),
                    ("accepted", "Accepted"),
                    ("declined", "Declined"),
                ],
                default="none",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="trainingsession",
            name="opponent_responded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="trainingsession",
            name="opponent_responded_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="responded_training_session_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="trainingsession",
            name="opponent_team",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="opponent_training_sessions",
                to="core.team",
            ),
        ),
    ]
