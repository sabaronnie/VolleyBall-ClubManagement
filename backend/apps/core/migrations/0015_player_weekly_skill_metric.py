import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0014_coach_dashboard_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlayerWeeklySkillMetric",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("week_start", models.DateField(help_text="Monday (ISO week start) for this data point.")),
                ("attack", models.DecimalField(decimal_places=2, max_digits=5)),
                ("defense", models.DecimalField(decimal_places=2, max_digits=5)),
                ("serve", models.DecimalField(decimal_places=2, max_digits=5)),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weekly_skill_metrics",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="player_weekly_skill_metrics",
                        to="core.team",
                    ),
                ),
            ],
            options={
                "ordering": ["player_id", "team_id", "week_start"],
            },
        ),
        migrations.AddConstraint(
            model_name="playerweeklyskillmetric",
            constraint=models.UniqueConstraint(
                fields=("player", "team", "week_start"),
                name="unique_player_team_week_skill_metric",
            ),
        ),
    ]
