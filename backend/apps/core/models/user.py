from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ObjectDoesNotExist
from django.db import models


class VerificationStatus(models.TextChoices):
    PENDING = "pending", "Pending director review"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class AssignedAccountRole(models.TextChoices):
    """Primary app role set by directors (kept in sync with club/team memberships where applicable)."""

    PLAYER = "player", "Player"
    PARENT = "parent", "Parent"
    COACH = "coach", "Coach"
    DIRECTOR = "director", "Director"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")

        requested_role = (extra_fields.pop("assigned_account_role", "") or "").strip().lower()
        email = self.normalize_email(email)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        if requested_role in AssignedAccountRole.values:
            from .user_account_role import UserAccountRole

            UserAccountRole.objects.update_or_create(
                user=user,
                defaults={"role": requested_role},
            )
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("verification_status", VerificationStatus.VERIFIED)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    date_of_birth = models.DateField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=30, blank=True)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.VERIFIED,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    @property
    def assigned_account_role(self) -> str:
        try:
            assignment = self.account_role_assignment
        except (AttributeError, ObjectDoesNotExist):
            assignment = None
        role = getattr(assignment, "role", "") or ""
        return role if role in AssignedAccountRole.values else ""

    def __str__(self) -> str:
        return self.get_full_name() or self.email
