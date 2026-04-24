from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_alter_tournament_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="teams_qualifying_per_pool",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
