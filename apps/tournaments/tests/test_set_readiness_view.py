import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.players.tests.factories import PairFactory, PlayerFactory
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

SET_READINESS_URL = "/api/v1/tournaments/{pk}/set-readiness/"


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
class TestTournamentSetReadinessView:
    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        tournament = TournamentFactory()
        response = api_client.get(SET_READINESS_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_other_user_tournament_returns_404(
        self, authenticated_client: APIClient, other_user
    ) -> None:
        tournament = TournamentFactory(owner=other_user)
        response = authenticated_client.get(SET_READINESS_URL.format(pk=tournament.pk))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_not_found_returns_404(self, authenticated_client: APIClient) -> None:
        response = authenticated_client.get(SET_READINESS_URL.format(pk=999999))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_tournament_ready_returns_200_with_empty_blockers(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(
            owner=user,
            game_format=Tournament.GameFormat.B1,
            configuration=Tournament.Configuration.TMC,
        )
        for i in range(4):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        response = authenticated_client.get(SET_READINESS_URL.format(pk=tournament.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_set_ready"] is True
        assert response.data["missing_configuration"] is False
        assert response.data["missing_game_format"] is False
        assert response.data["pairs_count"] == 4
        assert response.data["pairs_without_weight"] == []
        assert response.data["players_without_ranking"] == []

    def test_tournament_not_ready_returns_populated_blockers(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(
            owner=user,
            game_format="",
            configuration=Tournament.Configuration.TMC,
        )
        unweighted_pair = PairFactory(tournament=tournament, weight=None)
        for i in range(3):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        response = authenticated_client.get(SET_READINESS_URL.format(pk=tournament.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_set_ready"] is False
        assert response.data["missing_game_format"] is True
        assert response.data["missing_configuration"] is False
        assert response.data["pairs_count"] == 4
        assert len(response.data["pairs_without_weight"]) == 1
        assert response.data["pairs_without_weight"][0]["id"] == unweighted_pair.id
        assert "player1" in response.data["pairs_without_weight"][0]
        assert "player2" in response.data["pairs_without_weight"][0]

    def test_response_shape_matches_serializer_fields(
        self, authenticated_client: APIClient, user
    ) -> None:
        tournament = TournamentFactory(
            owner=user,
            game_format=Tournament.GameFormat.B1,
            configuration=Tournament.Configuration.TMC,
        )
        player_without_ranking = PlayerFactory(ranking=None)
        pair = PairFactory(
            tournament=tournament,
            weight=100.0,
            player1=player_without_ranking,
        )
        for i in range(3):
            PairFactory(tournament=tournament, weight=float(200 + i * 10))

        response = authenticated_client.get(SET_READINESS_URL.format(pk=tournament.pk))

        assert response.status_code == status.HTTP_200_OK
        assert set(response.data.keys()) == {
            "is_set_ready",
            "missing_configuration",
            "missing_game_format",
            "pairs_count",
            "pairs_without_weight",
            "players_without_ranking",
        }
        assert len(response.data["players_without_ranking"]) == 1
        entry = response.data["players_without_ranking"][0]
        assert set(entry.keys()) == {"pair_id", "player_id", "full_name"}
        assert entry["pair_id"] == pair.id
        assert entry["player_id"] == player_without_ranking.id
