from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_trainingsession_match_requests"),
    ]

    operations = [
        migrations.AddField(
            model_name="trainingsession",
            name="match_ended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="trainingsession",
            name="opponent_final_score",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
