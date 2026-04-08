from django.contrib.auth.models import AbstractUser
from django.db import models


# Inherited from AbstractUser so includes:
# username, first_name, last_name, password, is_active, is_staff,
# is_superuser, date_joined, last_login, groups, user_permissions
class User(AbstractUser):
    email = models.EmailField(unique=True)

    def __str__(self) -> str:
        return self.username
