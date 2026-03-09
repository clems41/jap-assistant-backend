import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

LIST_CREATE_URL = "/api/v1/tournaments/"
DETAIL_URL = "/api/v1/tournaments/{pk}"

CATEGORIES_URL = "/api/v1/tournaments/enums/categories"
LEAGUES_URL = "/api/v1/tournaments/enums/leagues"
GENDERS_URL = "/api/v1/tournaments/enums/genders"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def other_user():
    return UserFactory()


@pytest.fixture
def authenticated_client(api_client: APIClient, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def other_client(other_user):
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListTournaments:
    def test_list_tournaments_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        """GET /tournaments/ requires authentication."""
        response = api_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_tournaments_returns_only_own_tournaments(
        self, authenticated_client: APIClient, user, other_user
    ) -> None:
        """GET /tournaments/ returns only the authenticated user's tournaments."""
        TournamentFactory.create_batch(3, owner=user)
        TournamentFactory.create_batch(2, owner=other_user)
        response = authenticated_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_list_tournaments_returns_paginated_response(
        self, authenticated_client: APIClient, user
    ) -> None:
        TournamentFactory.create_batch(5, owner=user)
        response = authenticated_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data

    def test_list_tournaments_empty_for_new_user(
        self, authenticated_client: APIClient, other_user
    ) -> None:
        """A user with no tournaments sees an empty list, not other users' tournaments."""
        TournamentFactory.create_batch(3, owner=other_user)
        response = authenticated_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


VALID_PAYLOAD = {
    "name": "Open Sud",
    "category": "P100",
    "start_date": "2026-06-15",
    "location": "Marseille",
    "league": "Provence-Alpes-Côtes d'Azur",
    "gender": "Mixte",
}


@pytest.mark.django_db
class TestCreateTournament:
    def test_create_tournament_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        response = api_client.post(LIST_CREATE_URL, VALID_PAYLOAD, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_tournament_success(
        self, authenticated_client: APIClient, user
    ) -> None:
        response = authenticated_client.post(LIST_CREATE_URL, VALID_PAYLOAD, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Open Sud"
        assert response.data["category"] == "P100"
        assert response.data["start_date"] == "2026-06-15"
        assert response.data["location"] == "Marseille"
        assert response.data["league"] == "Provence-Alpes-Côtes d'Azur"
        assert response.data["gender"] == "Mixte"
        assert "id" in response.data
        assert "created_at" in response.data
        assert "updated_at" in response.data

    def test_create_tournament_owner_assigned_automatically(
        self, authenticated_client: APIClient, user
    ) -> None:
        """The owner must be set to request.user — not provided in the payload."""
        response = authenticated_client.post(LIST_CREATE_URL, VALID_PAYLOAD, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["owner"] == user.pk

    def test_create_tournament_cannot_forge_owner(
        self, authenticated_client: APIClient, user, other_user
    ) -> None:
        """Sending a different owner in the payload must be silently ignored."""
        payload = {**VALID_PAYLOAD, "owner": other_user.pk}
        response = authenticated_client.post(LIST_CREATE_URL, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["owner"] == user.pk

    def test_create_tournament_invalid_category_returns_400(
        self, authenticated_client: APIClient
    ) -> None:
        payload = {**VALID_PAYLOAD, "category": "P999"}
        response = authenticated_client.post(LIST_CREATE_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_tournament_invalid_league_returns_400(
        self, authenticated_client: APIClient
    ) -> None:
        payload = {**VALID_PAYLOAD, "league": "Atlantique"}
        response = authenticated_client.post(LIST_CREATE_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_tournament_invalid_gender_returns_400(
        self, authenticated_client: APIClient
    ) -> None:
        payload = {**VALID_PAYLOAD, "gender": "Unknown"}
        response = authenticated_client.post(LIST_CREATE_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_tournament_missing_name_returns_400(
        self, authenticated_client: APIClient
    ) -> None:
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "name"}
        response = authenticated_client.post(LIST_CREATE_URL, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Retrieve
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRetrieveTournament:
    def test_retrieve_tournament_unauthenticated_returns_401(
        self, api_client: APIClient, user
    ) -> None:
        """GET /tournaments/{id} requires authentication."""
        tournament = TournamentFactory(owner=user)
        response = api_client.get(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_own_tournament_success(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user)
        response = authenticated_client.get(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == tournament.pk
        assert response.data["name"] == tournament.name
        assert response.data["category"] == tournament.category
        assert response.data["location"] == tournament.location

    def test_retrieve_other_user_tournament_returns_404(
        self, authenticated_client: APIClient, other_user
    ) -> None:
        """A tournament owned by another user is invisible — filtered queryset returns 404."""
        tournament = TournamentFactory(owner=other_user)
        response = authenticated_client.get(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_tournament_not_found_returns_404(
        self, authenticated_client: APIClient
    ) -> None:
        response = authenticated_client.get(DETAIL_URL.format(pk=9999))
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUpdateTournament:
    UPDATE_PAYLOAD = {
        "name": "Updated Name",
        "category": "P250",
        "start_date": "2026-09-01",
        "location": "Lyon",
        "league": "Auvergne-Rhône-Alpes",
        "gender": "Homme",
    }

    def test_put_tournament_unauthenticated_returns_401(
        self, api_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user)
        response = api_client.put(
            DETAIL_URL.format(pk=tournament.pk), self.UPDATE_PAYLOAD, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_own_tournament_success(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user)
        response = authenticated_client.put(
            DETAIL_URL.format(pk=tournament.pk), self.UPDATE_PAYLOAD, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Name"
        assert response.data["category"] == "P250"
        assert response.data["league"] == "Auvergne-Rhône-Alpes"
        assert response.data["gender"] == "Homme"

    def test_put_other_user_tournament_returns_404(
        self, authenticated_client: APIClient, other_user
    ) -> None:
        tournament = TournamentFactory(owner=other_user)
        response = authenticated_client.put(
            DETAIL_URL.format(pk=tournament.pk), self.UPDATE_PAYLOAD, format="json"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_patch_tournament_unauthenticated_returns_401(
        self, api_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user)
        response = api_client.patch(
            DETAIL_URL.format(pk=tournament.pk), {"name": "Patched"}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_own_tournament_success(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user)
        response = authenticated_client.patch(
            DETAIL_URL.format(pk=tournament.pk),
            {"name": "Patched Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Patched Name"

    def test_patch_tournament_invalid_category_returns_400(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user)
        response = authenticated_client.patch(
            DETAIL_URL.format(pk=tournament.pk),
            {"category": "INVALID"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_other_user_tournament_returns_404(
        self, authenticated_client: APIClient, other_user
    ) -> None:
        tournament = TournamentFactory(owner=other_user)
        response = authenticated_client.patch(
            DETAIL_URL.format(pk=tournament.pk),
            {"name": "Should Fail"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeleteTournament:
    def test_delete_tournament_unauthenticated_returns_401(
        self, api_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user)
        response = api_client.delete(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_own_tournament_success(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user)
        response = authenticated_client.delete(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_other_user_tournament_returns_404(
        self, authenticated_client: APIClient, other_user
    ) -> None:
        tournament = TournamentFactory(owner=other_user)
        response = authenticated_client.delete(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_deleted_tournament_returns_404(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user)
        pk = tournament.pk
        authenticated_client.delete(DETAIL_URL.format(pk=pk))
        response = authenticated_client.get(DETAIL_URL.format(pk=pk))
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Enum endpoints
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEnumCategories:
    def test_list_categories_returns_200(self, api_client: APIClient) -> None:
        """GET /tournaments/enums/categories is public and returns 200."""
        response = api_client.get(CATEGORIES_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_list_categories_returns_all_categories(
        self, api_client: APIClient
    ) -> None:
        response = api_client.get(CATEGORIES_URL)
        assert len(response.data) == len(Tournament.Category)

    def test_list_categories_item_format(self, api_client: APIClient) -> None:
        """Each item must have 'value' and 'label' keys."""
        response = api_client.get(CATEGORIES_URL)
        first = response.data[0]
        assert "value" in first
        assert "label" in first

    def test_list_categories_p25_entry(self, api_client: APIClient) -> None:
        response = api_client.get(CATEGORIES_URL)
        values = {item["value"] for item in response.data}
        assert "P25" in values
        p25 = next(item for item in response.data if item["value"] == "P25")
        assert p25["label"] == "P25"

    def test_list_categories_no_auth_required(self, api_client: APIClient) -> None:
        """Endpoint must be accessible without JWT token."""
        response = api_client.get(CATEGORIES_URL)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    def test_list_categories_unknown_enum_returns_404(self, api_client: APIClient) -> None:
        response = api_client.get("/api/v1/tournaments/enums/unknown")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestEnumLeagues:
    def test_list_leagues_returns_200(self, api_client: APIClient) -> None:
        response = api_client.get(LEAGUES_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_list_leagues_returns_all_leagues(
        self, api_client: APIClient
    ) -> None:
        response = api_client.get(LEAGUES_URL)
        assert len(response.data) == len(Tournament.League)

    def test_list_leagues_item_format(self, api_client: APIClient) -> None:
        response = api_client.get(LEAGUES_URL)
        first = response.data[0]
        assert "value" in first
        assert "label" in first

    def test_list_leagues_bretagne_entry(self, api_client: APIClient) -> None:
        response = api_client.get(LEAGUES_URL)
        values = {item["value"] for item in response.data}
        assert "Bretagne" in values
        bretagne = next(item for item in response.data if item["value"] == "Bretagne")
        assert bretagne["label"] == "Bretagne"

    def test_list_leagues_no_auth_required(self, api_client: APIClient) -> None:
        response = api_client.get(LEAGUES_URL)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestEnumGenders:
    def test_list_genders_returns_200(self, api_client: APIClient) -> None:
        response = api_client.get(GENDERS_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_list_genders_returns_all_genders(
        self, api_client: APIClient
    ) -> None:
        response = api_client.get(GENDERS_URL)
        assert len(response.data) == len(Tournament.Gender)

    def test_list_genders_item_format(self, api_client: APIClient) -> None:
        response = api_client.get(GENDERS_URL)
        first = response.data[0]
        assert "value" in first
        assert "label" in first

    def test_list_genders_homme_entry(self, api_client: APIClient) -> None:
        response = api_client.get(GENDERS_URL)
        values = {item["value"] for item in response.data}
        assert "Homme" in values
        homme = next(item for item in response.data if item["value"] == "Homme")
        assert homme["label"] == "Homme"

    def test_list_genders_no_auth_required(self, api_client: APIClient) -> None:
        response = api_client.get(GENDERS_URL)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED
