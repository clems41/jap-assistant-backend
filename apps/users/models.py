import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class UserManager(DjangoUserManager):
    """Custom manager that uses email instead of username."""

    def _create_user(self, email: str, password: str | None, **extra_fields):  # type: ignore[override]
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):  # type: ignore[override]
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):  # type: ignore[override]
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model — email-only authentication, no username."""

    objects = UserManager()

    username = None  # type: ignore[assignment]
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return self.email


class PasswordResetToken(TimeStampedModel):
    """Single-use token for password reset. Valid for 1 hour."""

    TOKEN_EXPIRY = timedelta(hours=1)

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"

    def __str__(self) -> str:
        return f"PasswordResetToken({self.token}) for {self.user.email}"

    def is_valid(self) -> bool:
        """Return True if the token is not expired and not yet used."""
        if self.is_used:
            return False
        return timezone.now() < self.created_at + self.TOKEN_EXPIRY
