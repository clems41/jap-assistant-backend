"""
Auth endpoint tests — following TDD approach.
Tests are written first, implementation follows.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.tests.factories import UserFactory


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.mark.django_db
class TestRegister:
    url = reverse("auth-register")

    def test_register_success(self, client: APIClient) -> None:
        payload = {
            "email": "new@example.com",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }
        response = client.post(self.url, payload)
        assert response.status_code == status.HTTP_201_CREATED

    def test_register_password_mismatch(self, client: APIClient) -> None:
        payload = {
            "email": "new@example.com",
            "password": "StrongPass123!",
            "password_confirm": "WrongPass456!",
        }
        response = client.post(self.url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email(self, client: APIClient, user) -> None:
        payload = {
            "email": user.email,
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }
        response = client.post(self.url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTokenObtain:
    url = reverse("token-obtain-pair")

    def test_obtain_token_success(self, client: APIClient, user) -> None:
        response = client.post(self.url, {"email": user.email, "password": "testpass123"})
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_obtain_token_wrong_password(self, client: APIClient, user) -> None:
        response = client.post(self.url, {"email": user.email, "password": "wrongpass"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMe:
    url = reverse("auth-me")

    def test_me_authenticated(self, client: APIClient, user) -> None:
        client.force_authenticate(user=user)
        response = client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_me_unauthenticated(self, client: APIClient) -> None:
        response = client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
