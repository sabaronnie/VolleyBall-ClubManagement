import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import apps.core.models.team_invitation


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0017_rename_core_regist_email_9f6506_idx_core_regist_email_07ff9f_idx"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeamInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invited_email", models.EmailField(max_length=254)),
                ("role", models.CharField(choices=[("player", "Player"), ("coach", "Coach")], default="player", max_length=20)),
                ("code", models.CharField(default=apps.core.models.team_invitation._generate_code, max_length=128, unique=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined"), ("expired", "Expired")], default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(default=apps.core.models.team_invitation._default_expiry)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("invited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_team_invitations", to=settings.AUTH_USER_MODEL)),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitations", to="core.team")),
            ],
        ),
        migrations.AddIndex(
            model_name="teaminvitation",
            index=models.Index(fields=["code"], name="core_teamin_code_4ddd0f_idx"),
        ),
        migrations.AddIndex(
            model_name="teaminvitation",
            index=models.Index(fields=["team", "invited_email", "status"], name="core_teamin_team_id_d01703_idx"),
        ),
    ]
