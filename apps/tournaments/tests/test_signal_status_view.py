import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.tests.factories import UserFactory

SIGNAL_STATUS_URL = "/api/v1/tournaments/debug/signal-status/"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def authenticated_client(api_client: APIClient) -> APIClient:
    api_client.force_authenticate(user=UserFactory())
    return api_client


@pytest.mark.django_db
class TestSignalStatusView:
    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        response = api_client.get(SIGNAL_STATUS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_reports_registered_receiver_counts(
        self, authenticated_client: APIClient
    ) -> None:
        """In this test process, apps.tournaments.signals.register_signals() has
        run via AppConfig.ready() — so all 4 receivers it defines must be live,
        alongside the 2 pre-existing apps.players.signals receivers on Pair."""
        response = authenticated_client.get(SIGNAL_STATUS_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["tournament_post_save_count"] >= 1
        assert response.data["pair_post_save_count"] >= 2
        assert response.data["pair_post_delete_count"] >= 2
        assert response.data["player_post_save_count"] >= 1

    def test_raw_receivers_report_matching_sender_ids(
        self, authenticated_client: APIClient
    ) -> None:
        """In a single, freshly-loaded test process, register_signals() only
        ever runs once, so every raw entry's sender_id must match the current
        Tournament/Pair/Player class id."""
        response = authenticated_client.get(SIGNAL_STATUS_URL)

        assert response.status_code == status.HTTP_200_OK
        raw_receivers = response.data["raw_receivers"]
        assert len(raw_receivers) >= 4
        assert all(entry["alive"] for entry in raw_receivers)
        assert all(entry["sender_matches_current"] for entry in raw_receivers)
