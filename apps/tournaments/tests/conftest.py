import pytest
from rest_framework.test import APIClient

from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def authenticated_client(client: APIClient, user) -> APIClient:
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def tournament(user):
    return TournamentFactory(owner=user)
