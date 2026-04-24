import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def normalize_verification_statuses(apps, schema_editor):
    User = apps.get_model("core", "User")
    User.objects.exclude(verification_status__in=["pending", "verified", "rejected"]).update(
        verification_status="verified"
    )


def _column_exists(cursor, table, column):
    cursor.execute(
        """
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        [table, column],
    )
    return cursor.fetchone() is not None


def add_verification_status_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if _column_exists(cursor, "core_user", "verification_status"):
            return
        cursor.execute(
            "ALTER TABLE `core_user` ADD COLUMN `verification_status` varchar(20) NOT NULL DEFAULT 'verified'"
        )


def remove_verification_status_if_present(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if not _column_exists(cursor, "core_user", "verification_status"):
            return
        cursor.execute("ALTER TABLE `core_user` DROP COLUMN `verification_status`")


def add_assigned_account_role_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if _column_exists(cursor, "core_user", "assigned_account_role"):
            return
        cursor.execute(
            "ALTER TABLE `core_user` ADD COLUMN `assigned_account_role` varchar(20) NOT NULL DEFAULT ''"
        )


def remove_assigned_account_role_if_present(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if not _column_exists(cursor, "core_user", "assigned_account_role"):
            return
        cursor.execute("ALTER TABLE `core_user` DROP COLUMN `assigned_account_role`")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_notification"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="PasswordResetOTP",
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
                        ("otp_hash", models.CharField(max_length=128)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("expires_at", models.DateTimeField()),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="password_reset_otps",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "indexes": [
                            models.Index(
                                fields=["user", "expires_at"],
                                name="core_passwo_user_id_7b76f5_idx",
                            )
                        ],
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    CREATE TABLE IF NOT EXISTS `core_passwordresetotp` (
                        `id` bigint NOT NULL AUTO_INCREMENT,
                        `otp_hash` varchar(128) NOT NULL,
                        `created_at` datetime(6) NOT NULL,
                        `expires_at` datetime(6) NOT NULL,
                        `user_id` bigint NOT NULL,
                        PRIMARY KEY (`id`),
                        KEY `core_passwo_user_id_7b76f5_idx` (`user_id`, `expires_at`),
                        CONSTRAINT `core_passwordresetotp_user_id_fk`
                            FOREIGN KEY (`user_id`) REFERENCES `core_user` (`id`)
                            ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                    """,
                    reverse_sql="DROP TABLE IF EXISTS `core_passwordresetotp`;",
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="user",
                    name="verification_status",
                    field=models.CharField(
                        choices=[
                            ("pending", "Pending director review"),
                            ("verified", "Verified"),
                            ("rejected", "Rejected"),
                        ],
                        default="verified",
                        max_length=20,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_verification_status_if_missing, remove_verification_status_if_present),
            ],
        ),
        migrations.RunPython(normalize_verification_statuses, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="user",
                    name="assigned_account_role",
                    field=models.CharField(
                        blank=True,
                        choices=[
                            ("player", "Player"),
                            ("parent", "Parent"),
                            ("coach", "Coach"),
                        ],
                        default="",
                        help_text="Role chosen by a director when approving this account.",
                        max_length=20,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_assigned_account_role_if_missing, remove_assigned_account_role_if_present),
            ],
        ),
    ]
