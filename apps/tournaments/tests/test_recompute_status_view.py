import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.players.tests.factories import PairFactory
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

RECOMPUTE_STATUS_URL = "/api/v1/tournaments/{pk}/recompute-status/"


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


@pytest.mark.django_db
class TestTournamentRecomputeStatusView:
    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = api_client.post(RECOMPUTE_STATUS_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_other_user_tournament_returns_404(
        self, authenticated_client: APIClient, other_user
    ) -> None:
        tournament = TournamentFactory(owner=other_user)
        response = authenticated_client.post(RECOMPUTE_STATUS_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_not_found_returns_404(self, authenticated_client: APIClient) -> None:
        response = authenticated_client.post(RECOMPUTE_STATUS_URL.format(pk=999999))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_flips_draft_to_set_when_conditions_are_met(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(
            owner=user,
            game_format=Tournament.GameFormat.C1,
            configuration=Tournament.Configuration.TMC,
        )
        for i in range(4):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        # Force the status back to DRAFT bypassing signals, simulating a
        # tournament whose persisted status is stale relative to its data.
        Tournament.objects.filter(pk=tournament.pk).update(
            status=Tournament.Status.DRAFT
        )

        response = authenticated_client.post(RECOMPUTE_STATUS_URL.format(pk=tournament.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status_before"] == Tournament.Status.DRAFT
        assert response.data["status_after"] == Tournament.Status.SET

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

    def test_is_noop_when_status_already_correct(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user)

        response = authenticated_client.post(RECOMPUTE_STATUS_URL.format(pk=tournament.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status_before"] == Tournament.Status.DRAFT
        assert response.data["status_after"] == Tournament.Status.DRAFT

    def test_is_noop_when_tournament_is_started(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(owner=user, status=Tournament.Status.STARTED)

        response = authenticated_client.post(RECOMPUTE_STATUS_URL.format(pk=tournament.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status_before"] == Tournament.Status.STARTED
        assert response.data["status_after"] == Tournament.Status.STARTED
