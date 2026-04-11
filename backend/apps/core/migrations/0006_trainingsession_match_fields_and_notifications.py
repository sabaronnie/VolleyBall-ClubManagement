from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_teamscheduleentry_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="trainingsession",
            name="match_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("friendly", "Friendly"),
                    ("league", "League"),
                    ("tournament", "Tournament"),
                    ("scrimmage", "Scrimmage"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="trainingsession",
            name="notify_parents",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="trainingsession",
            name="notify_players",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="trainingsession",
            name="opponent",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
