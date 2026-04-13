import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_assigned_roles_to_side_table(apps, schema_editor):
    User = apps.get_model("core", "User")
    UserAccountRole = apps.get_model("core", "UserAccountRole")
    valid_roles = {"director", "coach", "player", "parent"}

    rows = []
    for user in User.objects.exclude(assigned_account_role="").iterator():
        role = (user.assigned_account_role or "").strip().lower()
        if role in valid_roles:
            rows.append(UserAccountRole(user_id=user.id, role=role))

    if rows:
        UserAccountRole.objects.bulk_create(rows, ignore_conflicts=True)


def normalize_user_verification_statuses(apps, schema_editor):
    User = apps.get_model("core", "User")
    User.objects.exclude(verification_status="verified").update(verification_status="verified")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_notification_attendance_incomplete"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegistrationOTP",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("first_name", models.CharField(max_length=150)),
                ("last_name", models.CharField(max_length=150)),
                ("date_of_birth", models.DateField()),
                ("password_hash", models.CharField(max_length=128)),
                ("otp_hash", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
            ],
        ),
        migrations.CreateModel(
            name="UserAccountRole",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("player", "Player"),
                            ("parent", "Parent"),
                            ("coach", "Coach"),
                            ("director", "Director"),
                        ],
                        max_length=20,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="account_role_assignment",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="registrationotp",
            index=models.Index(fields=["email", "expires_at"], name="core_regist_email_9f6506_idx"),
        ),
        migrations.AddIndex(
            model_name="useraccountrole",
            index=models.Index(fields=["role"], name="core_userac_role_f0e9d4_idx"),
        ),
        migrations.RunPython(copy_assigned_roles_to_side_table, migrations.RunPython.noop),
        migrations.RunPython(normalize_user_verification_statuses, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="user",
            name="assigned_account_role",
        ),
    ]
