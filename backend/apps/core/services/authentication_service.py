from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password

from apps.core.repositories.user_repository import UserRepository


class AuthenticationService:
    @staticmethod
    def hash_password(raw_password: str) -> str:
        # Django hashers include per-password salts automatically.
        return make_password(raw_password)

    @staticmethod
    def email_exists(email: str) -> bool:
        return UserRepository.exists_by_email(email)

    @staticmethod
    def login_user(*, request, email: str, password: str):
        return authenticate(request, email=email, password=password)
