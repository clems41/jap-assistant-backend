"""
Tests for the password reset feature.
Covers: PasswordResetToken model, request endpoint, confirm endpoint.
"""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.tests.factories import UserFactory

User = get_user_model()

PASSWORD_RESET_URL = "/api/v1/auth/password-reset/"
PASSWORD_RESET_CONFIRM_URL = "/api/v1/auth/password-reset/confirm/"


# ---------------------------------------------------------------------------
# PasswordResetToken model tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPasswordResetTokenModel:
    def test_token_is_valid_when_fresh(self):
        from apps.users.models import PasswordResetToken

        user = UserFactory()
        token = PasswordResetToken.objects.create(user=user)
        assert token.is_valid() is True

    def test_token_is_invalid_when_expired(self):
        from apps.users.models import PasswordResetToken

        user = UserFactory()
        token = PasswordResetToken.objects.create(user=user)
        # Force creation time to more than 1 hour ago
        PasswordResetToken.objects.filter(pk=token.pk).update(
            created_at=timezone.now() - timedelta(hours=1, minutes=1)
        )
        token.refresh_from_db()
        assert token.is_valid() is False

    def test_token_is_invalid_when_used(self):
        from apps.users.models import PasswordResetToken

        user = UserFactory()
        token = PasswordResetToken.objects.create(user=user, is_used=True)
        assert token.is_valid() is False

    def test_token_uuid_is_auto_generated(self):
        import uuid

        from apps.users.models import PasswordResetToken

        user = UserFactory()
        token = PasswordResetToken.objects.create(user=user)
        assert token.token is not None
        assert isinstance(token.token, uuid.UUID)

    def test_token_str_representation(self):
        from apps.users.models import PasswordResetToken

        user = UserFactory()
        token = PasswordResetToken.objects.create(user=user)
        assert str(token.token) in str(token)


# ---------------------------------------------------------------------------
# POST /api/v1/auth/password-reset/ — request tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPasswordResetRequestView:
    def setup_method(self):
        self.client = APIClient()

    def test_request_with_existing_email_returns_200(self):
        UserFactory(email="existing@example.com")
        response = self.client.post(
            PASSWORD_RESET_URL, {"email": "existing@example.com"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_request_with_existing_email_returns_generic_message(self):
        UserFactory(email="existing@example.com")
        response = self.client.post(
            PASSWORD_RESET_URL, {"email": "existing@example.com"}, format="json"
        )
        assert response.data["message"] == (
            "Si un compte existe avec cet email, vous recevrez un lien de réinitialisation."
        )

    def test_request_with_nonexistent_email_returns_200(self):
        response = self.client.post(
            PASSWORD_RESET_URL, {"email": "nobody@example.com"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_request_with_nonexistent_email_returns_same_generic_message(self):
        response = self.client.post(
            PASSWORD_RESET_URL, {"email": "nobody@example.com"}, format="json"
        )
        assert response.data["message"] == (
            "Si un compte existe avec cet email, vous recevrez un lien de réinitialisation."
        )

    def test_request_with_nonexistent_email_sends_no_email(self):
        self.client.post(
            PASSWORD_RESET_URL, {"email": "nobody@example.com"}, format="json"
        )
        assert len(mail.outbox) == 0

    def test_request_with_existing_email_sends_email(self):
        UserFactory(email="existing@example.com")
        self.client.post(
            PASSWORD_RESET_URL, {"email": "existing@example.com"}, format="json"
        )
        assert len(mail.outbox) == 1

    def test_request_with_existing_email_creates_token(self):
        from apps.users.models import PasswordResetToken

        user = UserFactory(email="existing@example.com")
        self.client.post(
            PASSWORD_RESET_URL, {"email": "existing@example.com"}, format="json"
        )
        assert PasswordResetToken.objects.filter(user=user).exists()

    def test_request_with_nonexistent_email_creates_no_token(self):
        from apps.users.models import PasswordResetToken

        self.client.post(
            PASSWORD_RESET_URL, {"email": "nobody@example.com"}, format="json"
        )
        assert PasswordResetToken.objects.count() == 0

    def test_request_email_contains_token_link(self):
        from apps.users.models import PasswordResetToken

        user = UserFactory(email="existing@example.com")
        self.client.post(
            PASSWORD_RESET_URL, {"email": "existing@example.com"}, format="json"
        )
        token = PasswordResetToken.objects.get(user=user)
        assert str(token.token) in mail.outbox[0].body

    def test_request_email_subject(self):
        UserFactory(email="existing@example.com")
        self.client.post(
            PASSWORD_RESET_URL, {"email": "existing@example.com"}, format="json"
        )
        assert mail.outbox[0].subject == "Réinitialisation de votre mot de passe"

    def test_request_with_invalid_email_format_returns_400(self):
        response = self.client.post(
            PASSWORD_RESET_URL, {"email": "not-an-email"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_request_without_email_returns_400(self):
        response = self.client.post(PASSWORD_RESET_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# POST /api/v1/auth/password-reset/confirm/ — confirm tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPasswordResetConfirmView:
    def setup_method(self):
        self.client = APIClient()

    def _create_valid_token(self, password: str = "testpass123") -> tuple:
        """Helper: returns (user, token_instance)."""
        from apps.users.models import PasswordResetToken

        user = UserFactory(password=password)
        token = PasswordResetToken.objects.create(user=user)
        return user, token

    def test_confirm_with_valid_token_returns_200(self):
        _, token = self._create_valid_token()
        response = self.client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {"token": str(token.token), "new_password": "NewSecurePass123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_confirm_with_valid_token_changes_password(self):
        user, token = self._create_valid_token()
        self.client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {"token": str(token.token), "new_password": "NewSecurePass123!"},
            format="json",
        )
        user.refresh_from_db()
        assert user.check_password("NewSecurePass123!")

    def test_confirm_marks_token_as_used(self):
        _, token = self._create_valid_token()
        self.client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {"token": str(token.token), "new_password": "NewSecurePass123!"},
            format="json",
        )
        token.refresh_from_db()
        assert token.is_used is True

    def test_confirm_with_nonexistent_token_returns_400(self):
        import uuid

        response = self.client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {"token": str(uuid.uuid4()), "new_password": "NewSecurePass123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_with_nonexistent_token_returns_correct_message(self):
        import uuid

        response = self.client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {"token": str(uuid.uuid4()), "new_password": "NewSecurePass123!"},
            format="json",
        )
        assert "invalide" in response.data["message"].lower() or "expiré" in response.data["message"].lower()

    def test_confirm_with_expired_token_returns_400(self):
        from apps.users.models import PasswordResetToken

        _, token = self._create_valid_token()
        PasswordResetToken.objects.filter(pk=token.pk).update(
            created_at=timezone.now() - timedelta(hours=1, minutes=1)
        )
        response = self.client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {"token": str(token.token), "new_password": "NewSecurePass123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_with_used_token_returns_400(self):
        from apps.users.models import PasswordResetToken

        user = UserFactory()
        token = PasswordResetToken.objects.create(user=user, is_used=True)
        response = self.client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {"token": str(token.token), "new_password": "NewSecurePass123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_with_too_short_password_returns_400(self):
        _, token = self._create_valid_token()
        response = self.client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {"token": str(token.token), "new_password": "short"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_success_allows_login_with_new_password(self):
        user, token = self._create_valid_token()
        self.client.post(
            PASSWORD_RESET_CONFIRM_URL,
            {"token": str(token.token), "new_password": "NewSecurePass123!"},
            format="json",
        )
        user.refresh_from_db()
        assert user.check_password("NewSecurePass123!")
        assert not user.check_password("testpass123")
