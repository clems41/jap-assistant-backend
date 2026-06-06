"""
Tests for automatic pairs_count maintenance on Tournament.

Business rule:
  tournament.pairs_count must always equal the number of Pair objects
  associated with that tournament.

The field is updated via Django signals on Pair post_save (created only)
and post_delete.
"""

import pytest
from rest_framework.test import APIClient

from apps.players.models import Pair
from apps.players.tests.factories import PairFactory, PlayerFactory
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

TOURNAMENTS_URL = "/api/v1/tournaments/"
TOURNAMENT_DETAIL_URL = "/api/v1/tournaments/{pk}/"
PAIRS_URL = "/api/v1/tournaments/{tournament_id}/pairs/"
PAIR_DETAIL_URL = "/api/v1/tournaments/{tournament_id}/pairs/{pk}/"


def tournament_detail_url(pk: int) -> str:
    return TOURNAMENT_DETAIL_URL.format(pk=pk)


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
# TestPairsCountInitialValue
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairsCountInitialValue:
    def test_new_tournament_has_zero_pairs_count(self, tournament):
        tournament.refresh_from_db()
        assert tournament.pairs_count == 0


# ---------------------------------------------------------------------------
# TestPairsCountOnCreate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairsCountOnCreate:
    def test_creating_pair_increments_count(self, tournament):
        PairFactory(tournament=tournament)

        tournament.refresh_from_db()
        assert tournament.pairs_count == 1

    def test_creating_multiple_pairs_increments_count_correctly(self, tournament):
        PairFactory(tournament=tournament)
        PairFactory(tournament=tournament)
        PairFactory(tournament=tournament)

        tournament.refresh_from_db()
        assert tournament.pairs_count == 3

    def test_pairs_count_is_scoped_per_tournament(self, tournament):
        other_tournament = TournamentFactory()
        PairFactory(tournament=tournament)
        PairFactory(tournament=other_tournament)
        PairFactory(tournament=other_tournament)

        tournament.refresh_from_db()
        other_tournament.refresh_from_db()
        assert tournament.pairs_count == 1
        assert other_tournament.pairs_count == 2


# ---------------------------------------------------------------------------
# TestPairsCountOnDelete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairsCountOnDelete:
    def test_deleting_pair_decrements_count(self, tournament):
        pair = PairFactory(tournament=tournament)
        tournament.refresh_from_db()
        assert tournament.pairs_count == 1

        pair.delete()

        tournament.refresh_from_db()
        assert tournament.pairs_count == 0

    def test_deleting_one_of_many_pairs_decrements_correctly(self, tournament):
        pair1 = PairFactory(tournament=tournament)
        PairFactory(tournament=tournament)
        PairFactory(tournament=tournament)
        tournament.refresh_from_db()
        assert tournament.pairs_count == 3

        pair1.delete()

        tournament.refresh_from_db()
        assert tournament.pairs_count == 2


# ---------------------------------------------------------------------------
# TestPairsCountOnUpdate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairsCountOnUpdate:
    def test_updating_pair_does_not_change_count(self, tournament):
        pair = PairFactory(tournament=tournament)
        tournament.refresh_from_db()
        assert tournament.pairs_count == 1

        pair.weight = 999.0
        pair.save()

        tournament.refresh_from_db()
        assert tournament.pairs_count == 1


# ---------------------------------------------------------------------------
# TestPairsCountViaAPI
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairsCountViaAPI:
    def test_pairs_count_exposed_in_tournament_api(self, auth_client, tournament):
        PairFactory(tournament=tournament)
        PairFactory(tournament=tournament)

        response = auth_client.get(tournament_detail_url(tournament.pk))

        assert response.status_code == 200
        assert response.data["pairs_count"] == 2

    def test_pairs_count_updates_after_pair_created_via_api(
        self, auth_client, tournament
    ):
        player1 = PlayerFactory(ranking=100)
        player2 = PlayerFactory(ranking=200)

        auth_client.post(
            pairs_url(tournament.pk),
            {
                "player1": {
                    "last_name": player1.last_name,
                    "first_name": player1.first_name,
                    "license_number": player1.license_number,
                    "ranking": player1.ranking,
                },
                "player2": {
                    "last_name": player2.last_name,
                    "first_name": player2.first_name,
                    "license_number": player2.license_number,
                    "ranking": player2.ranking,
                },
            },
            format="json",
        )

        response = auth_client.get(tournament_detail_url(tournament.pk))
        assert response.data["pairs_count"] == 1

    def test_pairs_count_updates_after_pair_deleted_via_api(
        self, auth_client, tournament
    ):
        pair = PairFactory(tournament=tournament)
        tournament.refresh_from_db()
        assert tournament.pairs_count == 1

        auth_client.delete(pair_detail_url(tournament.pk, pair.pk))

        response = auth_client.get(tournament_detail_url(tournament.pk))
        assert response.data["pairs_count"] == 0
