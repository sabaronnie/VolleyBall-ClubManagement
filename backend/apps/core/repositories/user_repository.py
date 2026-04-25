from django.contrib.auth import get_user_model


User = get_user_model()


class UserRepository:
    @staticmethod
    def get_by_email(email: str):
        return User.objects.filter(email=email).first()

    @staticmethod
    def exists_by_email(email: str) -> bool:
        return User.objects.filter(email=email).exists()
