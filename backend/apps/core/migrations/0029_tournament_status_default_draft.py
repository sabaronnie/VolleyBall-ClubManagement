from django.db import migrations, models


def migrate_generated_to_draft(apps, schema_editor):
    Tournament = apps.get_model("core", "Tournament")
    Tournament.objects.filter(status="generated").update(status="draft")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_alter_tournament_status_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_generated_to_draft, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tournament",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pool_stage", "Pool Stage"),
                    ("bracket_stage", "Bracket Stage"),
                    ("completed", "Completed"),
                    ("generated", "Generated"),
                    ("cancelled", "Cancelled"),
                ],
                default="draft",
                max_length=16,
            ),
        ),
    ]
