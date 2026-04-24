from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_trainingsession_trainingsessionconfirmation"),
    ]

    operations = [
        migrations.AddField(
            model_name="teamscheduleentry",
            name="location",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
