"""
Tests for automatic weight calculation on Pair create/update.

Business rule:
  weight = player1.ranking + player2.ranking

The calculation must trigger automatically when rankings are provided.
If either ranking is missing (None), weight stays unchanged.
"""

import pytest
from rest_framework.test import APIClient

from apps.players.tests.factories import PairFactory, PlayerFactory
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

PAIRS_URL = "/api/v1/tournaments/{tournament_id}/pairs/"
PAIR_DETAIL_URL = "/api/v1/tournaments/{tournament_id}/pairs/{pk}/"


def pairs_url(tournament_id: int) -> str:
    return PAIRS_URL.format(tournament_id=tournament_id)


def pair_detail_url(tournament_id: int, pk: int) -> str:
    return PAIR_DETAIL_URL.format(tournament_id=tournament_id, pk=pk)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def tournament(user):
    return TournamentFactory(owner=user)


# ---------------------------------------------------------------------------
# TestPairWeightCalculationOnCreate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairWeightCalculationOnCreate:
    def test_create_pair_weight_auto_calculated_from_rankings(
        self, auth_client, tournament
    ):
        """When both players have rankings, weight = ranking1 + ranking2 on create."""
        payload = {
            "player1": {
                "last_name": "Martin",
                "first_name": "Julien",
                "license_number": "WC_CREATE001",
                "phone": "",
                "ranking": 300,
            },
            "player2": {
                "last_name": "Roux",
                "first_name": "Quentin",
                "license_number": "WC_CREATE002",
                "phone": "",
                "ranking": 200,
            },
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        assert response.data["weight"] == 500.0

    def test_create_pair_weight_not_calculated_when_player1_ranking_missing(
        self, auth_client, tournament
    ):
        """When player1 has no ranking, weight stays None (no calculation)."""
        payload = {
            "player1": {
                "last_name": "Martin",
                "first_name": "Julien",
                "license_number": "WC_CREATE003",
                "phone": "",
                "ranking": None,
            },
            "player2": {
                "last_name": "Roux",
                "first_name": "Quentin",
                "license_number": "WC_CREATE004",
                "phone": "",
                "ranking": 200,
            },
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        assert response.data["weight"] is None

    def test_create_pair_weight_not_calculated_when_player2_ranking_missing(
        self, auth_client, tournament
    ):
        """When player2 has no ranking, weight stays None (no calculation)."""
        payload = {
            "player1": {
                "last_name": "Martin",
                "first_name": "Julien",
                "license_number": "WC_CREATE005",
                "phone": "",
                "ranking": 300,
            },
            "player2": {
                "last_name": "Roux",
                "first_name": "Quentin",
                "license_number": "WC_CREATE006",
                "phone": "",
                "ranking": None,
            },
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        assert response.data["weight"] is None

    def test_create_pair_explicit_weight_overridden_by_rankings(
        self, auth_client, tournament
    ):
        """When both rankings are provided, they override any explicit weight value."""
        payload = {
            "player1": {
                "last_name": "Martin",
                "first_name": "Julien",
                "license_number": "WC_CREATE007",
                "phone": "",
                "ranking": 400,
            },
            "player2": {
                "last_name": "Roux",
                "first_name": "Quentin",
                "license_number": "WC_CREATE008",
                "phone": "",
                "ranking": 100,
            },
            "weight": 999.9,
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        assert response.data["weight"] == 500.0


# ---------------------------------------------------------------------------
# TestPairWeightCalculationOnUpdate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairWeightCalculationOnUpdate:
    def test_patch_with_rankings_recalculates_weight(self, auth_client, tournament):
        """PATCH with rankings for both players recalculates weight automatically."""
        pair = PairFactory(tournament=tournament, weight=100.0)
        payload = {
            "player1": {
                "last_name": pair.player1.last_name,
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": 350,
            },
            "player2": {
                "last_name": pair.player2.last_name,
                "first_name": pair.player2.first_name,
                "license_number": pair.player2.license_number,
                "phone": pair.player2.phone,
                "ranking": 150,
            },
        }
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["weight"] == 500.0

    def test_patch_only_weight_does_not_trigger_recalculation(
        self, auth_client, tournament
    ):
        """PATCH with only weight (no player rankings) keeps the provided weight."""
        pair = PairFactory(tournament=tournament, weight=100.0)
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id),
            data={"weight": 750.0},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["weight"] == 750.0

    def test_patch_with_only_player1_ranking_does_not_recalculate(
        self, auth_client, tournament
    ):
        """PATCH providing ranking only for player1 does not recalculate weight."""
        player2 = PlayerFactory(ranking=None)
        pair = PairFactory(tournament=tournament, player2=player2, weight=100.0)
        payload = {
            "player1": {
                "last_name": pair.player1.last_name,
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": 400,
            },
        }
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200
        # player2 has no ranking, so no auto-calc — weight should be unchanged
        assert response.data["weight"] == 100.0

    def test_put_with_rankings_recalculates_weight(self, auth_client, tournament):
        """PUT with rankings for both players recalculates weight automatically."""
        pair = PairFactory(tournament=tournament, weight=100.0)
        payload = {
            "player1": {
                "last_name": "Alpha",
                "first_name": "Un",
                "license_number": "WC_PUT001",
                "phone": "",
                "ranking": 600,
            },
            "player2": {
                "last_name": "Beta",
                "first_name": "Deux",
                "license_number": "WC_PUT002",
                "phone": "",
                "ranking": 400,
            },
        }
        response = auth_client.put(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["weight"] == 1000.0

    def test_patch_updates_player_ranking_in_db(self, auth_client, tournament):
        """PATCH with a new ranking actually persists the player ranking to the DB."""
        pair = PairFactory(tournament=tournament)
        pair.player1.ranking = 100
        pair.player1.save()
        pair.player2.ranking = 200
        pair.player2.save()

        payload = {
            "player1": {
                "last_name": pair.player1.last_name,
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": 450,
            },
            "player2": {
                "last_name": pair.player2.last_name,
                "first_name": pair.player2.first_name,
                "license_number": pair.player2.license_number,
                "phone": pair.player2.phone,
                "ranking": 550,
            },
        }
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["weight"] == 1000.0

        pair.player1.refresh_from_db()
        pair.player2.refresh_from_db()
        assert pair.player1.ranking == 450
        assert pair.player2.ranking == 550
