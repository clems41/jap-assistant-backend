from datetime import time

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tournaments.models import TimeSlot, Tournament
from apps.tournaments.tests.factories import TimeSlotFactory, TournamentFactory
from apps.users.tests.factories import UserFactory

LIST_CREATE_URL = "/api/v1/tournaments/"
DETAIL_URL = "/api/v1/tournaments/{pk}/"

CATEGORIES_URL = "/api/v1/tournaments/enums/categories/"
LEAGUES_URL = "/api/v1/tournaments/enums/leagues/"
GENDERS_URL = "/api/v1/tournaments/enums/genders/"
CONFIGURATIONS_URL = "/api/v1/tournaments/enums/configurations/"


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
    def test_list_tournaments_unauthenticated_returns_401(
        self, api_client: APIClient
    ) -> None:
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
    def test_create_tournament_unauthenticated_returns_401(
        self, api_client: APIClient
    ) -> None:
        response = api_client.post(LIST_CREATE_URL, VALID_PAYLOAD, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_tournament_success(
        self, authenticated_client: APIClient, user
    ) -> None:
        response = authenticated_client.post(
            LIST_CREATE_URL, VALID_PAYLOAD, format="json"
        )
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
        response = authenticated_client.post(
            LIST_CREATE_URL, VALID_PAYLOAD, format="json"
        )
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

    def test_patch_started_tournament_returns_409(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user, status=Tournament.Status.STARTED)
        response = authenticated_client.patch(
            DETAIL_URL.format(pk=tournament.pk),
            {"name": "Should Fail"},
            format="json",
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_patch_finished_tournament_returns_409(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user, status=Tournament.Status.FINISHED)
        response = authenticated_client.patch(
            DETAIL_URL.format(pk=tournament.pk),
            {"name": "Should Fail"},
            format="json",
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_put_started_tournament_returns_409(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user, status=Tournament.Status.STARTED)
        response = authenticated_client.put(
            DETAIL_URL.format(pk=tournament.pk), self.UPDATE_PAYLOAD, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_put_finished_tournament_returns_409(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user, status=Tournament.Status.FINISHED)
        response = authenticated_client.put(
            DETAIL_URL.format(pk=tournament.pk), self.UPDATE_PAYLOAD, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_patch_draft_tournament_still_succeeds(
        self, authenticated_client: APIClient, user
    ) -> None:
        """Regression: DRAFT status must remain editable."""
        tournament = TournamentFactory(owner=user, status=Tournament.Status.DRAFT)
        response = authenticated_client.patch(
            DETAIL_URL.format(pk=tournament.pk),
            {"name": "Patched Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_patch_set_tournament_still_succeeds(
        self, authenticated_client: APIClient, user
    ) -> None:
        """Regression: SET status must remain editable."""
        tournament = TournamentFactory(owner=user, status=Tournament.Status.SET)
        response = authenticated_client.patch(
            DETAIL_URL.format(pk=tournament.pk),
            {"name": "Patched Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


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

    def test_delete_started_tournament_returns_409(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user, status=Tournament.Status.STARTED)
        response = authenticated_client.delete(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_409_CONFLICT
        assert Tournament.objects.filter(pk=tournament.pk).exists()

    def test_delete_finished_tournament_returns_409(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user, status=Tournament.Status.FINISHED)
        response = authenticated_client.delete(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_409_CONFLICT
        assert Tournament.objects.filter(pk=tournament.pk).exists()

    def test_delete_draft_tournament_still_succeeds(
        self, authenticated_client: APIClient, user
    ) -> None:
        """Regression: DRAFT status must remain deletable."""
        tournament = TournamentFactory(owner=user, status=Tournament.Status.DRAFT)
        response = authenticated_client.delete(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_set_tournament_still_succeeds(
        self, authenticated_client: APIClient, user
    ) -> None:
        """Regression: SET status must remain deletable."""
        tournament = TournamentFactory(owner=user, status=Tournament.Status.SET)
        response = authenticated_client.delete(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_204_NO_CONTENT


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

    def test_list_categories_unknown_enum_returns_404(
        self, api_client: APIClient
    ) -> None:
        response = api_client.get("/api/v1/tournaments/enums/unknown")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestEnumLeagues:
    def test_list_leagues_returns_200(self, api_client: APIClient) -> None:
        response = api_client.get(LEAGUES_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_list_leagues_returns_all_leagues(self, api_client: APIClient) -> None:
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

    def test_list_genders_returns_all_genders(self, api_client: APIClient) -> None:
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


GAME_FORMATS_URL = "/api/v1/tournaments/enums/game-formats/"


@pytest.mark.django_db
class TestEnumGameFormats:
    def test_list_game_formats_returns_200(self, api_client: APIClient) -> None:
        """GET /tournaments/enums/game-formats/ is public and returns 200."""
        response = api_client.get(GAME_FORMATS_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_list_game_formats_returns_all_game_formats(
        self, api_client: APIClient
    ) -> None:
        response = api_client.get(GAME_FORMATS_URL)
        assert len(response.data) == len(Tournament.GameFormat)

    def test_list_game_formats_item_format(self, api_client: APIClient) -> None:
        """Each item must have 'value' and 'label' keys."""
        response = api_client.get(GAME_FORMATS_URL)
        first = response.data[0]
        assert "value" in first
        assert "label" in first

    def test_list_game_formats_a1_entry(self, api_client: APIClient) -> None:
        response = api_client.get(GAME_FORMATS_URL)
        values = {item["value"] for item in response.data}
        assert "A1" in values
        a1 = next(item for item in response.data if item["value"] == "A1")
        assert a1["label"] == "A1 : 3 sets à 6 jeux, jeu décisif à 6-6"

    def test_list_game_formats_no_auth_required(self, api_client: APIClient) -> None:
        response = api_client.get(GAME_FORMATS_URL)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestEnumConfigurations:
    def test_list_configurations_returns_200(self, api_client: APIClient) -> None:
        res = api_client.get(CONFIGURATIONS_URL)
        assert res.status_code == status.HTTP_200_OK

    def test_list_configurations_returns_all_configurations(
        self, api_client: APIClient
    ) -> None:
        res = api_client.get(CONFIGURATIONS_URL)
        assert len(res.data) == len(Tournament.Configuration)

    def test_list_configurations_item_format(self, api_client: APIClient) -> None:
        res = api_client.get(CONFIGURATIONS_URL)
        item = res.data[0]
        assert set(item.keys()) == {"value", "label"}

    def test_list_configurations_tmc_entry(self, api_client: APIClient) -> None:
        res = api_client.get(CONFIGURATIONS_URL)
        assert {"value": "TMC", "label": "Tournoi Multi Chance (TMC)"} in res.data

    def test_list_configurations_no_auth_required(self, api_client: APIClient) -> None:
        res = api_client.get(CONFIGURATIONS_URL)
        assert res.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Last information
# ---------------------------------------------------------------------------

INFORMATIONS_URL = "/api/v1/tournaments/informations/"

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFilterTournaments:
    def test_filter_by_category_returns_matching_tournaments(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?category=P100 returns only P100 tournaments."""
        TournamentFactory.create_batch(2, owner=user, category=Tournament.Category.P100)
        TournamentFactory.create_batch(3, owner=user, category=Tournament.Category.P250)
        response = authenticated_client.get(LIST_CREATE_URL, {"category": "P100"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert all(t["category"] == "P100" for t in response.data["results"])

    def test_filter_by_category_no_match_returns_empty(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?category=P500 returns empty list when no P500 tournaments exist."""
        TournamentFactory.create_batch(2, owner=user, category=Tournament.Category.P100)
        response = authenticated_client.get(LIST_CREATE_URL, {"category": "P500"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_filter_by_gender_returns_matching_tournaments(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?gender=Homme returns only male tournaments."""
        TournamentFactory.create_batch(2, owner=user, gender=Tournament.Gender.MALE)
        TournamentFactory.create_batch(1, owner=user, gender=Tournament.Gender.FEMALE)
        TournamentFactory.create_batch(1, owner=user, gender=Tournament.Gender.MIXED)
        response = authenticated_client.get(LIST_CREATE_URL, {"gender": "Homme"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert all(t["gender"] == "Homme" for t in response.data["results"])

    def test_filter_by_gender_no_match_returns_empty(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?gender=Femme returns empty list when no female tournaments exist."""
        TournamentFactory.create_batch(2, owner=user, gender=Tournament.Gender.MALE)
        response = authenticated_client.get(LIST_CREATE_URL, {"gender": "Femme"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_filter_by_start_date_lower_bound(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?start_date=2026-06-01 returns tournaments whose start_date >= 2026-06-01."""
        TournamentFactory(owner=user, start_date="2026-05-15")
        TournamentFactory(owner=user, start_date="2026-06-01")
        TournamentFactory(owner=user, start_date="2026-07-10")
        response = authenticated_client.get(
            LIST_CREATE_URL, {"start_date": "2026-06-01"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        for t in response.data["results"]:
            assert t["start_date"] >= "2026-06-01"

    def test_filter_by_end_date_upper_bound(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?end_date=2026-06-30 returns tournaments whose start_date <= 2026-06-30."""
        TournamentFactory(owner=user, start_date="2026-05-15")
        TournamentFactory(owner=user, start_date="2026-06-30")
        TournamentFactory(owner=user, start_date="2026-07-10")
        response = authenticated_client.get(LIST_CREATE_URL, {"end_date": "2026-06-30"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        for t in response.data["results"]:
            assert t["start_date"] <= "2026-06-30"

    def test_filter_by_start_date_and_end_date_range(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?start_date=2026-06-01&end_date=2026-06-30 returns tournaments in that range."""
        TournamentFactory(owner=user, start_date="2026-05-15")
        TournamentFactory(owner=user, start_date="2026-06-10")
        TournamentFactory(owner=user, start_date="2026-06-30")
        TournamentFactory(owner=user, start_date="2026-07-01")
        response = authenticated_client.get(
            LIST_CREATE_URL, {"start_date": "2026-06-01", "end_date": "2026-06-30"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        for t in response.data["results"]:
            assert "2026-06-01" <= t["start_date"] <= "2026-06-30"

    def test_filter_combined_category_and_gender(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?category=P100&gender=Homme returns only P100 male tournaments."""
        TournamentFactory(
            owner=user, category=Tournament.Category.P100, gender=Tournament.Gender.MALE
        )
        TournamentFactory(
            owner=user,
            category=Tournament.Category.P100,
            gender=Tournament.Gender.FEMALE,
        )
        TournamentFactory(
            owner=user, category=Tournament.Category.P250, gender=Tournament.Gender.MALE
        )
        response = authenticated_client.get(
            LIST_CREATE_URL, {"category": "P100", "gender": "Homme"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["category"] == "P100"
        assert response.data["results"][0]["gender"] == "Homme"

    def test_filters_only_apply_to_own_tournaments(
        self, authenticated_client: APIClient, user, other_user
    ) -> None:
        """Filters must never expose another user's tournaments."""
        TournamentFactory(owner=user, category=Tournament.Category.P100)
        TournamentFactory(owner=other_user, category=Tournament.Category.P100)
        response = authenticated_client.get(LIST_CREATE_URL, {"category": "P100"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_filter_no_params_returns_all_own_tournaments(
        self, authenticated_client: APIClient, user
    ) -> None:
        """No filter params → same behaviour as before (all own tournaments)."""
        TournamentFactory.create_batch(4, owner=user)
        response = authenticated_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 4

    def test_filter_by_status_returns_matching_tournaments(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?status=DRAFT returns only DRAFT tournaments."""
        TournamentFactory.create_batch(2, owner=user, status=Tournament.Status.DRAFT)
        TournamentFactory.create_batch(1, owner=user, status=Tournament.Status.STARTED)
        response = authenticated_client.get(LIST_CREATE_URL, {"status": "DRAFT"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert all(t["status"] == "DRAFT" for t in response.data["results"])

    def test_filter_by_status_no_match_returns_empty(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?status=FINISHED returns empty list when no finished tournaments exist."""
        TournamentFactory.create_batch(2, owner=user, status=Tournament.Status.DRAFT)
        response = authenticated_client.get(LIST_CREATE_URL, {"status": "FINISHED"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListTournamentsOrdering:
    def test_list_tournaments_ordered_by_start_date_ascending(
        self, authenticated_client: APIClient, user
    ) -> None:
        """GET /tournaments/ returns tournaments sorted by start_date ascending by default."""
        TournamentFactory(owner=user, start_date="2026-09-01")
        TournamentFactory(owner=user, start_date="2026-03-15")
        TournamentFactory(owner=user, start_date="2026-06-10")
        response = authenticated_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_200_OK
        dates = [t["start_date"] for t in response.data["results"]]
        assert dates == sorted(dates)

    def test_list_tournaments_most_recent_start_date_last(
        self, authenticated_client: APIClient, user
    ) -> None:
        """The tournament with the latest start_date appears last in the list."""
        latest = TournamentFactory(owner=user, start_date="2026-12-31")
        TournamentFactory(owner=user, start_date="2026-01-01")
        TournamentFactory(owner=user, start_date="2026-06-15")
        response = authenticated_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_200_OK
        last_result = response.data["results"][-1]
        assert last_result["id"] == latest.pk

    def test_ordering_by_start_date_descending(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?ordering=-start_date returns tournaments with the most recent start_date first."""
        TournamentFactory(owner=user, start_date="2026-03-01")
        TournamentFactory(owner=user, start_date="2026-09-01")
        TournamentFactory(owner=user, start_date="2026-06-01")
        response = authenticated_client.get(
            LIST_CREATE_URL, {"ordering": "-start_date"}
        )
        assert response.status_code == status.HTTP_200_OK
        dates = [t["start_date"] for t in response.data["results"]]
        assert dates == sorted(dates, reverse=True)

    def test_ordering_by_name_ascending(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?ordering=name returns tournaments sorted alphabetically by name."""
        TournamentFactory(owner=user, name="Zeta Cup", start_date="2026-06-01")
        TournamentFactory(owner=user, name="Alpha Open", start_date="2026-06-01")
        TournamentFactory(owner=user, name="Metro Classic", start_date="2026-06-01")
        response = authenticated_client.get(LIST_CREATE_URL, {"ordering": "name"})
        assert response.status_code == status.HTTP_200_OK
        names = [t["name"] for t in response.data["results"]]
        assert names == sorted(names)

    def test_ordering_by_name_descending(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?ordering=-name returns tournaments sorted reverse-alphabetically."""
        TournamentFactory(owner=user, name="Zeta Cup", start_date="2026-06-01")
        TournamentFactory(owner=user, name="Alpha Open", start_date="2026-06-01")
        TournamentFactory(owner=user, name="Metro Classic", start_date="2026-06-01")
        response = authenticated_client.get(LIST_CREATE_URL, {"ordering": "-name"})
        assert response.status_code == status.HTTP_200_OK
        names = [t["name"] for t in response.data["results"]]
        assert names == sorted(names, reverse=True)

    def test_ordering_by_created_at_descending(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?ordering=-created_at returns newest-created tournaments first."""
        t1 = TournamentFactory(owner=user, start_date="2026-06-01")
        t2 = TournamentFactory(owner=user, start_date="2026-06-02")
        t3 = TournamentFactory(owner=user, start_date="2026-06-03")
        response = authenticated_client.get(
            LIST_CREATE_URL, {"ordering": "-created_at"}
        )
        assert response.status_code == status.HTTP_200_OK
        ids = [t["id"] for t in response.data["results"]]
        # Created in order t1, t2, t3 — descending means t3, t2, t1
        assert ids == [t3.pk, t2.pk, t1.pk]

    def test_ordering_invalid_field_ignored(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?ordering=nonexistent_field is silently ignored (falls back to default order)."""
        TournamentFactory.create_batch(3, owner=user)
        response = authenticated_client.get(
            LIST_CREATE_URL, {"ordering": "nonexistent_field"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3


# ---------------------------------------------------------------------------
# Page size
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListTournamentsPageSize:
    def test_page_size_limits_results(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?page_size=2 returns at most 2 results per page."""
        TournamentFactory.create_batch(5, owner=user)
        response = authenticated_client.get(LIST_CREATE_URL, {"page_size": 2})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2
        assert response.data["count"] == 5
        assert response.data["next"] is not None

    def test_page_size_one_returns_single_result(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?page_size=1 returns exactly 1 result."""
        TournamentFactory.create_batch(3, owner=user)
        response = authenticated_client.get(LIST_CREATE_URL, {"page_size": 1})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_page_size_larger_than_total_returns_all(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?page_size=100 with 3 tournaments returns all 3, no next page."""
        TournamentFactory.create_batch(3, owner=user)
        response = authenticated_client.get(LIST_CREATE_URL, {"page_size": 100})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3
        assert response.data["next"] is None

    def test_page_size_above_max_is_capped(
        self, authenticated_client: APIClient, user
    ) -> None:
        """?page_size=200 is capped to max_page_size (100) — returns at most 100 results."""
        TournamentFactory.create_batch(5, owner=user)
        response = authenticated_client.get(LIST_CREATE_URL, {"page_size": 200})
        assert response.status_code == status.HTTP_200_OK
        # Capped — no error, response is valid, results <= max_page_size
        assert len(response.data["results"]) <= 100

    def test_default_page_size_is_20(
        self, authenticated_client: APIClient, user
    ) -> None:
        """Without ?page_size, the default page size is 20."""
        TournamentFactory.create_batch(25, owner=user)
        response = authenticated_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 20
        assert response.data["count"] == 25
        assert response.data["next"] is not None


@pytest.mark.django_db
class TestInformations:
    def test_informations_unauthenticated_returns_401(
        self, api_client: APIClient
    ) -> None:
        """GET /tournaments/informations requires authentication."""
        response = api_client.get(INFORMATIONS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_informations_no_tournament_returns_null_and_empty_list(
        self, authenticated_client: APIClient
    ) -> None:
        """When the user has no tournament, fields must be null/empty — not a 404."""
        response = authenticated_client.get(INFORMATIONS_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "last_league": None,
            "last_location": None,
            "all_locations": [],
        }

    def test_informations_returns_fields_of_most_recent_tournament(
        self, authenticated_client: APIClient, user
    ) -> None:
        """Returns the league and location of the most recently created tournament."""
        TournamentFactory(
            owner=user, league=Tournament.League.BRETAGNE, location="Rennes"
        )
        TournamentFactory(
            owner=user, league=Tournament.League.NORMANDIE, location="Rouen"
        )
        response = authenticated_client.get(INFORMATIONS_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["last_league"] == Tournament.League.NORMANDIE
        assert response.data["last_location"] == "Rouen"

    def test_informations_ignores_other_users_tournaments(
        self, authenticated_client: APIClient, user, other_user
    ) -> None:
        """Only the authenticated user's tournaments are considered."""
        TournamentFactory(
            owner=other_user, league=Tournament.League.BRETAGNE, location="Rennes"
        )
        response = authenticated_client.get(INFORMATIONS_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "last_league": None,
            "last_location": None,
            "all_locations": [],
        }

    def test_informations_response_shape(
        self, authenticated_client: APIClient, user
    ) -> None:
        """Response contains 'last_league', 'last_location' and 'all_locations' keys."""
        TournamentFactory(
            owner=user, league=Tournament.League.ILE_DE_FRANCE, location="Paris"
        )
        response = authenticated_client.get(INFORMATIONS_URL)
        assert response.status_code == status.HTTP_200_OK
        assert set(response.data.keys()) == {
            "last_league",
            "last_location",
            "all_locations",
        }

    def test_informations_all_locations_deduplicates_identical_locations(
        self, authenticated_client: APIClient, user
    ) -> None:
        """Locations are deduplicated even if used by multiple tournaments."""
        TournamentFactory(owner=user, location="Paris")
        TournamentFactory(owner=user, location="Paris")
        TournamentFactory(owner=user, location="Lyon")
        response = authenticated_client.get(INFORMATIONS_URL)
        assert response.status_code == status.HTTP_200_OK
        all_locations = response.data["all_locations"]
        assert all_locations.count("Paris") == 1
        assert sorted(all_locations) == ["Lyon", "Paris"]

    def test_informations_all_locations_ordered_by_most_recent_usage_first(
        self, authenticated_client: APIClient, user
    ) -> None:
        """Locations are ordered by the most recent tournament using them."""
        TournamentFactory(owner=user, location="Paris")
        TournamentFactory(owner=user, location="Lyon")
        TournamentFactory(owner=user, location="Paris")
        response = authenticated_client.get(INFORMATIONS_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["all_locations"] == ["Paris", "Lyon"]

    def test_informations_all_locations_empty_when_no_tournament(
        self, authenticated_client: APIClient
    ) -> None:
        """all_locations is an empty list when the user has no tournament."""
        response = authenticated_client.get(INFORMATIONS_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["all_locations"] == []

    def test_informations_all_locations_ignores_other_users_tournaments(
        self, authenticated_client: APIClient, user, other_user
    ) -> None:
        """Other users' locations must not appear in all_locations."""
        TournamentFactory(owner=other_user, location="Marseille")
        TournamentFactory(owner=user, location="Paris")
        response = authenticated_client.get(INFORMATIONS_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["all_locations"] == ["Paris"]


# ---------------------------------------------------------------------------
# Game format durations enum
# ---------------------------------------------------------------------------

GAME_FORMAT_DURATIONS_URL = "/api/v1/tournaments/enums/game-format-durations/"


@pytest.mark.django_db
class TestGameFormatDurationEnum:
    def test_get_game_format_durations_returns_200(self, api_client: APIClient) -> None:
        """GET /tournaments/enums/game-format-durations/ is public and returns 200."""
        response = api_client.get(GAME_FORMAT_DURATIONS_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_get_game_format_durations_no_auth_required(
        self, api_client: APIClient
    ) -> None:
        response = api_client.get(GAME_FORMAT_DURATIONS_URL)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED

    def test_get_game_format_durations_returns_all_10_formats(
        self, api_client: APIClient
    ) -> None:
        response = api_client.get(GAME_FORMAT_DURATIONS_URL)
        assert len(response.data) == len(Tournament.GameFormat)

    def test_get_game_format_durations_item_has_format_and_duration_keys(
        self, api_client: APIClient
    ) -> None:
        response = api_client.get(GAME_FORMAT_DURATIONS_URL)
        first = response.data[0]
        assert "format" in first
        assert "duration" in first

    def test_get_game_format_durations_values_are_correct(
        self, api_client: APIClient
    ) -> None:
        response = api_client.get(GAME_FORMAT_DURATIONS_URL)
        by_format = {item["format"]: item["duration"] for item in response.data}
        assert by_format["A1"] == 100
        assert by_format["A2"] == 90
        assert by_format["B1"] == 70
        assert by_format["B2"] == 60
        assert by_format["C1"] == 50
        assert by_format["C2"] == 45
        assert by_format["D1"] == 50
        assert by_format["D2"] == 45
        assert by_format["E"] == 20
        assert by_format["F"] == 25


@pytest.mark.django_db
class TestEstimatedMatchDuration:
    def test_tournament_response_includes_estimated_match_duration_field(
        self, authenticated_client: APIClient, user
    ) -> None:
        """GET /tournaments/{id}/ response includes the estimated_match_duration field."""
        tournament = TournamentFactory(owner=user)
        response = authenticated_client.get(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_200_OK
        assert "estimated_match_duration" in response.data

    def test_patch_estimated_match_duration(
        self, authenticated_client: APIClient, user
    ) -> None:
        """PATCH estimated_match_duration updates the field."""
        tournament = TournamentFactory(owner=user)
        response = authenticated_client.patch(
            DETAIL_URL.format(pk=tournament.pk),
            {"estimated_match_duration": 55},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["estimated_match_duration"] == 55


# ---------------------------------------------------------------------------
# Time slots
# ---------------------------------------------------------------------------

TIME_SLOTS_LIST_URL = "/api/v1/tournaments/{tournament_id}/time-slots/"
TIME_SLOTS_DETAIL_URL = "/api/v1/tournaments/{tournament_id}/time-slots/{pk}/"

VALID_SLOT_PAYLOAD = {
    "start_time": "09:00:00",
    "end_time": "11:00:00",
    "courts_available": 4,
}


@pytest.mark.django_db
class TestTimeSlotListCreate:
    def test_list_requires_authentication(self, client, tournament) -> None:
        url = TIME_SLOTS_LIST_URL.format(tournament_id=tournament.pk)
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_returns_all_slots_without_pagination(
        self, authenticated_client, tournament
    ) -> None:
        TimeSlotFactory(tournament=tournament)
        TimeSlotFactory(tournament=tournament)
        url = TIME_SLOTS_LIST_URL.format(tournament_id=tournament.pk)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        assert len(response.data) == 2

    def test_list_returns_only_slots_of_own_tournament(
        self, authenticated_client, tournament
    ) -> None:
        TimeSlotFactory(tournament=tournament)
        TimeSlotFactory(tournament=tournament)
        other_tournament = TournamentFactory()
        TimeSlotFactory(tournament=other_tournament)
        url = TIME_SLOTS_LIST_URL.format(tournament_id=tournament.pk)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_list_tournament_not_found_returns_404(self, authenticated_client) -> None:
        url = TIME_SLOTS_LIST_URL.format(tournament_id=99999)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_other_user_tournament_returns_404(self, authenticated_client) -> None:
        other_tournament = TournamentFactory()
        url = TIME_SLOTS_LIST_URL.format(tournament_id=other_tournament.pk)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_requires_authentication(self, client, tournament) -> None:
        url = TIME_SLOTS_LIST_URL.format(tournament_id=tournament.pk)
        response = client.post(url, data=VALID_SLOT_PAYLOAD, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_success(self, authenticated_client, tournament) -> None:
        url = TIME_SLOTS_LIST_URL.format(tournament_id=tournament.pk)
        response = authenticated_client.post(
            url, data=VALID_SLOT_PAYLOAD, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["start_time"] == "09:00:00"
        assert response.data["end_time"] == "11:00:00"
        assert response.data["courts_available"] == 4
        assert response.data["tournament"] == tournament.pk

    def test_create_tournament_not_found_returns_404(
        self, authenticated_client
    ) -> None:
        url = TIME_SLOTS_LIST_URL.format(tournament_id=99999)
        response = authenticated_client.post(
            url, data=VALID_SLOT_PAYLOAD, format="json"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_other_user_tournament_returns_404(
        self, authenticated_client
    ) -> None:
        other_tournament = TournamentFactory()
        url = TIME_SLOTS_LIST_URL.format(tournament_id=other_tournament.pk)
        response = authenticated_client.post(
            url, data=VALID_SLOT_PAYLOAD, format="json"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_end_before_start_returns_400(
        self, authenticated_client, tournament
    ) -> None:
        url = TIME_SLOTS_LIST_URL.format(tournament_id=tournament.pk)
        payload = {
            "start_time": "11:00:00",
            "end_time": "09:00:00",
            "courts_available": 4,
        }
        response = authenticated_client.post(url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_equal_times_returns_400(
        self, authenticated_client, tournament
    ) -> None:
        url = TIME_SLOTS_LIST_URL.format(tournament_id=tournament.pk)
        payload = {
            "start_time": "09:00:00",
            "end_time": "09:00:00",
            "courts_available": 4,
        }
        response = authenticated_client.post(url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_missing_field_returns_400(
        self, authenticated_client, tournament
    ) -> None:
        url = TIME_SLOTS_LIST_URL.format(tournament_id=tournament.pk)
        payload = {"start_time": "09:00:00", "end_time": "11:00:00"}
        response = authenticated_client.post(url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTimeSlotDetail:
    def test_retrieve_requires_authentication(self, client, tournament) -> None:
        slot = TimeSlotFactory(tournament=tournament)
        url = TIME_SLOTS_DETAIL_URL.format(tournament_id=tournament.pk, pk=slot.pk)
        response = client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_own_slot_returns_200(
        self, authenticated_client, tournament
    ) -> None:
        slot = TimeSlotFactory(
            tournament=tournament,
            start_time=time(9, 0),
            end_time=time(11, 0),
            courts_available=3,
        )
        url = TIME_SLOTS_DETAIL_URL.format(tournament_id=tournament.pk, pk=slot.pk)
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == slot.pk
        assert response.data["courts_available"] == 3

    def test_retrieve_other_user_slot_returns_404(self, authenticated_client) -> None:
        other_tournament = TournamentFactory()
        slot = TimeSlotFactory(tournament=other_tournament)
        url = TIME_SLOTS_DETAIL_URL.format(
            tournament_id=other_tournament.pk, pk=slot.pk
        )
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_success(self, authenticated_client, tournament) -> None:
        slot = TimeSlotFactory(tournament=tournament)
        url = TIME_SLOTS_DETAIL_URL.format(tournament_id=tournament.pk, pk=slot.pk)
        payload = {
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "courts_available": 6,
        }
        response = authenticated_client.put(url, data=payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["courts_available"] == 6

    def test_partial_update_success(self, authenticated_client, tournament) -> None:
        slot = TimeSlotFactory(tournament=tournament, courts_available=2)
        url = TIME_SLOTS_DETAIL_URL.format(tournament_id=tournament.pk, pk=slot.pk)
        response = authenticated_client.patch(
            url, data={"courts_available": 8}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["courts_available"] == 8

    def test_update_end_before_start_returns_400(
        self, authenticated_client, tournament
    ) -> None:
        slot = TimeSlotFactory(tournament=tournament)
        url = TIME_SLOTS_DETAIL_URL.format(tournament_id=tournament.pk, pk=slot.pk)
        payload = {
            "start_time": "12:00:00",
            "end_time": "09:00:00",
            "courts_available": 4,
        }
        response = authenticated_client.put(url, data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_other_user_slot_returns_404(self, authenticated_client) -> None:
        other_tournament = TournamentFactory()
        slot = TimeSlotFactory(tournament=other_tournament)
        url = TIME_SLOTS_DETAIL_URL.format(
            tournament_id=other_tournament.pk, pk=slot.pk
        )
        payload = {
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "courts_available": 2,
        }
        response = authenticated_client.put(url, data=payload, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_own_slot_returns_204(
        self, authenticated_client, tournament
    ) -> None:
        slot = TimeSlotFactory(tournament=tournament)
        url = TIME_SLOTS_DETAIL_URL.format(tournament_id=tournament.pk, pk=slot.pk)
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not TimeSlot.objects.filter(pk=slot.pk).exists()

    def test_delete_other_user_slot_returns_404(self, authenticated_client) -> None:
        other_tournament = TournamentFactory()
        slot = TimeSlotFactory(tournament=other_tournament)
        url = TIME_SLOTS_DETAIL_URL.format(
            tournament_id=other_tournament.pk, pk=slot.pk
        )
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# QR code URL
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestQrCodeUrl:
    def test_retrieve_tournament_includes_qr_code_url(
        self, authenticated_client: APIClient, user, settings
    ) -> None:
        """GET /tournaments/{id}/ exposes qr_code_url pointing to the public matches page."""
        tournament = TournamentFactory(owner=user)
        response = authenticated_client.get(DETAIL_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_200_OK
        expected = (
            f"{settings.FRONTEND_URL}/public/tournaments/"
            f"{tournament.public_code}"
        )
        assert response.data["qr_code_url"] == expected

    def test_list_tournaments_includes_qr_code_url(
        self, authenticated_client: APIClient, user, settings
    ) -> None:
        """GET /tournaments/ also exposes qr_code_url on each item (shared serializer)."""
        TournamentFactory.create_batch(2, owner=user)
        response = authenticated_client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_200_OK
        for item in response.data["results"]:
            assert "qr_code_url" in item
            assert item["qr_code_url"].startswith(settings.FRONTEND_URL)

    def test_qr_code_url_differs_per_tournament(
        self, authenticated_client: APIClient, user
    ) -> None:
        """Two different tournaments must get two different qr_code_url values,
        each containing their own public_code."""
        tournament_a = TournamentFactory(owner=user)
        tournament_b = TournamentFactory(owner=user)
        response_a = authenticated_client.get(DETAIL_URL.format(pk=tournament_a.pk))
        response_b = authenticated_client.get(DETAIL_URL.format(pk=tournament_b.pk))
        assert response_a.data["qr_code_url"] != response_b.data["qr_code_url"]
        assert tournament_a.public_code in response_a.data["qr_code_url"]
        assert tournament_b.public_code in response_b.data["qr_code_url"]

    def test_qr_code_url_is_read_only(
        self, authenticated_client: APIClient, user, settings
    ) -> None:
        """A PATCH attempting to override qr_code_url must be silently ignored."""
        tournament = TournamentFactory(owner=user)
        response = authenticated_client.patch(
            DETAIL_URL.format(pk=tournament.pk),
            {"qr_code_url": "https://evil.example.com/hack"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        expected = (
            f"{settings.FRONTEND_URL}/public/tournaments/"
            f"{tournament.public_code}"
        )
        assert response.data["qr_code_url"] == expected
