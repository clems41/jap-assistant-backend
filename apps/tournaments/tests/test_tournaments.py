import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory


LIST_CREATE_URL = "/api/v1/tournaments"
DETAIL_URL = "/api/v1/tournaments/{pk}"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def authenticated_client(api_client: APIClient) -> APIClient:
    user = UserFactory()
    api_client.force_authenticate(user=user)
    return api_client


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TestListTournaments:
    @pytest.mark.django_db
    def test_list_tournaments_authenticated(self, authenticated_client: APIClient) -> None:
        TournamentFactory.create_batch(3)
        response = authenticated_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_200_OK
        assert "results" in response.data
        assert response.data["count"] == 3

    @pytest.mark.django_db
    def test_list_tournaments_unauthenticated(self, api_client: APIClient) -> None:
        response = api_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateTournament:
    valid_payload = {
        "name": "Open Sud",
        "category": "P100",
        "start_date": "2026-06-15",
        "location": "Marseille",
        "league": "Provence-Alpes-Côtes d'Azur",
        "gender": "Mixed",
    }

    @pytest.mark.django_db
    def test_create_tournament_success(self, authenticated_client: APIClient) -> None:
        response = authenticated_client.post(LIST_CREATE_URL, self.valid_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Open Sud"
        assert response.data["category"] == "P100"

    @pytest.mark.django_db
    def test_create_tournament_invalid_category(self, authenticated_client: APIClient) -> None:
        payload = {**self.valid_payload, "category": "P999"}
        response = authenticated_client.post(LIST_CREATE_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_create_tournament_invalid_league(self, authenticated_client: APIClient) -> None:
        payload = {**self.valid_payload, "league": "Atlantique"}
        response = authenticated_client.post(LIST_CREATE_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_create_tournament_missing_field(self, authenticated_client: APIClient) -> None:
        payload = {k: v for k, v in self.valid_payload.items() if k != "name"}
        response = authenticated_client.post(LIST_CREATE_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Retrieve
# ---------------------------------------------------------------------------


class TestRetrieveTournament:
    @pytest.mark.django_db
    def test_retrieve_tournament(self, authenticated_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = authenticated_client.get(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == tournament.pk
        assert response.data["name"] == tournament.name

    @pytest.mark.django_db
    def test_retrieve_tournament_not_found(self, authenticated_client: APIClient) -> None:
        response = authenticated_client.get(DETAIL_URL.format(pk=9999))
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdateTournament:
    @pytest.mark.django_db
    def test_update_tournament(self, authenticated_client: APIClient) -> None:
        tournament = TournamentFactory()
        payload = {
            "name": "Updated Name",
            "category": "P250",
            "start_date": "2026-09-01",
            "location": "Lyon",
            "league": "Auvergne-Rhône-Alpes",
            "gender": "Male",
        }
        response = authenticated_client.put(DETAIL_URL.format(pk=tournament.pk), payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Name"
        assert response.data["category"] == "P250"

    @pytest.mark.django_db
    def test_partial_update_tournament(self, authenticated_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = authenticated_client.patch(
            DETAIL_URL.format(pk=tournament.pk),
            {"name": "Patched Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Patched Name"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteTournament:
    @pytest.mark.django_db
    def test_delete_tournament(self, authenticated_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = authenticated_client.delete(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.django_db
    def test_delete_tournament_not_found(self, authenticated_client: APIClient) -> None:
        response = authenticated_client.delete(DETAIL_URL.format(pk=9999))
        assert response.status_code == status.HTTP_404_NOT_FOUND
