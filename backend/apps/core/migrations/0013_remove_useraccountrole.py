from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_registration_otp_and_user_role_assignment"),
    ]

    operations = [
        migrations.DeleteModel(
            name="UserAccountRole",
        ),
    ]
