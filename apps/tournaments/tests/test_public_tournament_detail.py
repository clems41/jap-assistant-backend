import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory

EXPECTED_FIELDS = {
    "public_code",
    "name",
    "category",
    "start_date",
    "location",
    "league",
    "gender",
    "game_format",
    "configuration",
    "estimated_match_duration",
    "status",
    "pairs_count",
}


def _detail_url(code: str) -> str:
    return f"/api/v1/public/tournaments/{code}/"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestPublicTournamentDetail:
    def test_retrieve_returns_200(self, api_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = api_client.get(_detail_url(tournament.public_code))
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_returns_exact_field_set(self, api_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = api_client.get(_detail_url(tournament.public_code))
        assert set(response.data.keys()) == EXPECTED_FIELDS

    def test_retrieve_does_not_expose_internal_fields(
        self, api_client: APIClient
    ) -> None:
        tournament = TournamentFactory()
        response = api_client.get(_detail_url(tournament.public_code))
        assert "id" not in response.data
        assert "owner" not in response.data
        assert "created_at" not in response.data
        assert "updated_at" not in response.data

    def test_retrieve_returns_correct_values(self, api_client: APIClient) -> None:
        tournament = TournamentFactory(
            name="Open Sud",
            category=Tournament.Category.P100,
            location="Marseille",
        )
        response = api_client.get(_detail_url(tournament.public_code))
        assert response.data["public_code"] == tournament.public_code
        assert response.data["name"] == "Open Sud"
        assert response.data["category"] == "P100"
        assert response.data["location"] == "Marseille"

    def test_retrieve_unknown_code_returns_404(self, api_client: APIClient) -> None:
        response = api_client.get(_detail_url("ZZZZZZZZ"))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_no_auth_required(self, api_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = api_client.get(_detail_url(tournament.public_code))
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    def test_retrieve_is_case_insensitive(self, api_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = api_client.get(_detail_url(tournament.public_code.lower()))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["public_code"] == tournament.public_code

    def test_post_returns_405(self, api_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = api_client.post(_detail_url(tournament.public_code), {})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_returns_405(self, api_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = api_client.patch(_detail_url(tournament.public_code), {})
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_returns_405(self, api_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = api_client.delete(_detail_url(tournament.public_code))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
