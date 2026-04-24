from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0019_player_parent_invitation"),
    ]

    operations = [
        migrations.CreateModel(
            name="MatchPlayerStat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("points_scored", models.PositiveIntegerField(default=0)),
                ("aces", models.PositiveIntegerField(default=0)),
                ("blocks", models.PositiveIntegerField(default=0)),
                ("assists", models.PositiveIntegerField(default=0)),
                ("errors", models.PositiveIntegerField(default=0)),
                ("digs", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="match_player_stats",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "training_session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="match_player_stats",
                        to="core.trainingsession",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_match_player_stats",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["player__first_name", "player__last_name", "player__email"],
            },
        ),
        migrations.AddConstraint(
            model_name="matchplayerstat",
            constraint=models.UniqueConstraint(
                fields=("training_session", "player"),
                name="unique_match_stat_per_session_player",
            ),
        ),
    ]
