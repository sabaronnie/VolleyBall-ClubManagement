from django.conf import settings
from django.core import signing


AUTH_TOKEN_SALT = "apps.core.auth"


def generate_auth_token(user):
    return signing.dumps(
        {
            "user_id": user.pk,
            "email": user.email,
        },
        salt=AUTH_TOKEN_SALT,
        compress=True,
    )


def verify_auth_token(token):
    max_age = getattr(settings, "AUTH_TOKEN_MAX_AGE", 60 * 60 * 24)
    return signing.loads(token, salt=AUTH_TOKEN_SALT, max_age=max_age)

