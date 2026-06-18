import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
def other_user():
    return UserFactory()


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def tournament(user):
    return TournamentFactory(owner=user)


@pytest.fixture
def other_tournament(other_user):
    return TournamentFactory(owner=other_user)


@pytest.fixture
def pair(tournament):
    from apps.players.tests.factories import PairFactory
    return PairFactory(tournament=tournament)


@pytest.fixture
def pair_payload():
    return {
        "player1": {
            "last_name": "Martin",
            "first_name": "Julien",
            "license_number": "LIC9990001",
            "phone": "0612345678",
            "ranking": 250,
        },
        "player2": {
            "last_name": "Roux",
            "first_name": "Quentin",
            "license_number": "LIC9990002",
            "phone": "0677889900",
            "ranking": 310,
        },
        "weight": 560.0,
    }


# ---------------------------------------------------------------------------
# TestListPairs
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestListPairs:
    def test_list_pairs_requires_auth(self, tournament):
        client = APIClient()
        response = client.get(pairs_url(tournament.id))
        assert response.status_code == 401

    def test_list_pairs_success(self, auth_client, tournament, pair):
        response = auth_client.get(pairs_url(tournament.id))
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_list_pairs_returns_flat_list_not_paginated(self, auth_client, tournament, pair):
        response = auth_client.get(pairs_url(tournament.id))
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert "count" not in response.data
        assert "next" not in response.data
        assert "previous" not in response.data
        assert "results" not in response.data

    def test_list_pairs_only_shows_own_tournament(self, auth_client, other_tournament):
        response = auth_client.get(pairs_url(other_tournament.id))
        assert response.status_code == 404

    def test_list_pairs_isolated_between_tournaments(self, auth_client, user, tournament):
        from apps.players.tests.factories import PairFactory
        second_tournament = TournamentFactory(owner=user)
        PairFactory(tournament=tournament)
        PairFactory(tournament=second_tournament)

        response = auth_client.get(pairs_url(tournament.id))
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_list_pairs_empty(self, auth_client, tournament):
        response = auth_client.get(pairs_url(tournament.id))
        assert response.status_code == 200
        assert response.data == []


# ---------------------------------------------------------------------------
# TestCreatePair
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCreatePair:
    def test_create_pair_requires_auth(self, tournament, pair_payload):
        client = APIClient()
        response = client.post(pairs_url(tournament.id), data=pair_payload, format="json")
        assert response.status_code == 401

    def test_create_pair_success(self, auth_client, tournament, pair_payload):
        response = auth_client.post(pairs_url(tournament.id), data=pair_payload, format="json")
        assert response.status_code == 201
        assert response.data["player1"]["license_number"] == "LIC9990001"
        assert response.data["player2"]["license_number"] == "LIC9990002"
        assert response.data["weight"] == 560.0

    def test_create_pair_ownership_check(self, auth_client, other_tournament, pair_payload):
        response = auth_client.post(pairs_url(other_tournament.id), data=pair_payload, format="json")
        assert response.status_code == 404

    def test_create_pair_same_player_twice(self, auth_client, tournament, pair_payload):
        payload = pair_payload.copy()
        payload["player2"] = payload["player1"].copy()
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 400

    def test_create_pair_player1_already_in_tournament(self, auth_client, tournament, pair):
        payload = {
            "player1": {
                "last_name": pair.player1.last_name,
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": pair.player1.ranking,
            },
            "player2": {
                "last_name": "Dupont",
                "first_name": "Marie",
                "license_number": "LIC9999999",
                "phone": "0611223344",
                "ranking": 180,
            },
            "weight": 600.0,
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 400

    def test_create_pair_player2_already_in_tournament(self, auth_client, tournament, pair):
        payload = {
            "player1": {
                "last_name": "Dupont",
                "first_name": "Marie",
                "license_number": "LIC9999998",
                "phone": "0611223344",
                "ranking": 180,
            },
            "player2": {
                "last_name": pair.player2.last_name,
                "first_name": pair.player2.first_name,
                "license_number": pair.player2.license_number,
                "phone": pair.player2.phone,
                "ranking": pair.player2.ranking,
            },
            "weight": 600.0,
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 400

    def test_create_pair_tournament_field_ignored(self, auth_client, tournament, other_tournament, pair_payload):
        payload = pair_payload.copy()
        payload["tournament"] = other_tournament.id
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        from apps.players.models import Pair
        created = Pair.objects.get(id=response.data["id"])
        assert created.tournament_id == tournament.id

    def test_create_pair_creates_player_if_not_exists(self, auth_client, tournament):
        from apps.players.models import Player
        payload = {
            "player1": {
                "last_name": "Nouveau",
                "first_name": "Joueur",
                "license_number": "NEWLIC001",
                "phone": "",
                "ranking": None,
            },
            "player2": {
                "last_name": "Autre",
                "first_name": "Joueur",
                "license_number": "NEWLIC002",
                "phone": "",
                "ranking": None,
            },
            "weight": None,
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        assert Player.objects.filter(license_number="NEWLIC001").exists()
        assert Player.objects.filter(license_number="NEWLIC002").exists()

    def test_create_pair_updates_player_if_exists(self, auth_client, tournament):
        from apps.players.models import Player
        player = Player.objects.create(
            last_name="Ancien",
            first_name="Nom",
            license_number="EXISTLIC001",
            phone="",
            ranking=100,
        )
        payload = {
            "player1": {
                "last_name": "Nouveau",
                "first_name": "Nom",
                "license_number": "EXISTLIC001",
                "phone": "",
                "ranking": 200,
            },
            "player2": {
                "last_name": "Autre",
                "first_name": "Joueur",
                "license_number": "EXISTLIC002",
                "phone": "",
                "ranking": None,
            },
            "weight": None,
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        player.refresh_from_db()
        assert player.last_name == "Nouveau"
        assert player.ranking == 200

    def test_create_pair_weight_none_when_no_rankings(self, auth_client, tournament):
        """Weight stays None when both players have no ranking."""
        payload = {
            "player1": {
                "last_name": "Martin",
                "first_name": "Julien",
                "license_number": "LIC_WO_RANK1",
                "phone": "",
                "ranking": None,
            },
            "player2": {
                "last_name": "Roux",
                "first_name": "Quentin",
                "license_number": "LIC_WO_RANK2",
                "phone": "",
                "ranking": None,
            },
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        assert response.data["weight"] is None

    def test_create_pair_returns_409_when_tournament_started(self, auth_client, tournament, pair_payload):
        from apps.players.models import Pair
        tournament.status = Tournament.Status.STARTED
        tournament.save()
        response = auth_client.post(pairs_url(tournament.id), data=pair_payload, format="json")
        assert response.status_code == 409
        assert not Pair.objects.filter(tournament=tournament).exists()

    def test_create_pair_returns_409_when_tournament_finished(self, auth_client, tournament, pair_payload):
        from apps.players.models import Pair
        tournament.status = Tournament.Status.FINISHED
        tournament.save()
        response = auth_client.post(pairs_url(tournament.id), data=pair_payload, format="json")
        assert response.status_code == 409
        assert not Pair.objects.filter(tournament=tournament).exists()


# ---------------------------------------------------------------------------
# TestRetrievePair
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRetrievePair:
    def test_retrieve_pair_requires_auth(self, tournament, pair):
        client = APIClient()
        response = client.get(pair_detail_url(tournament.id, pair.id))
        assert response.status_code == 401

    def test_retrieve_pair_success(self, auth_client, tournament, pair):
        response = auth_client.get(pair_detail_url(tournament.id, pair.id))
        assert response.status_code == 200
        assert response.data["id"] == pair.id

    def test_retrieve_pair_ownership_check(self, auth_client, other_tournament):
        from apps.players.tests.factories import PairFactory
        other_pair = PairFactory(tournament=other_tournament)
        response = auth_client.get(pair_detail_url(other_tournament.id, other_pair.id))
        assert response.status_code == 404

    def test_retrieve_pair_wrong_tournament(self, auth_client, user, tournament, pair):
        second_tournament = TournamentFactory(owner=user)
        response = auth_client.get(pair_detail_url(second_tournament.id, pair.id))
        assert response.status_code == 404

    def test_retrieve_pair_fields(self, auth_client, tournament, pair):
        response = auth_client.get(pair_detail_url(tournament.id, pair.id))
        assert response.status_code == 200
        data = response.data
        assert "id" in data
        assert "player1" in data
        assert "player2" in data
        assert "weight" in data
        assert "created_at" in data
        assert "updated_at" in data


# ---------------------------------------------------------------------------
# TestUpdatePair
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpdatePair:
    def test_update_pair_requires_auth(self, tournament, pair, pair_payload):
        client = APIClient()
        response = client.put(pair_detail_url(tournament.id, pair.id), data=pair_payload, format="json")
        assert response.status_code == 401

    def test_update_pair_put_success(self, auth_client, tournament, pair, pair_payload):
        response = auth_client.put(pair_detail_url(tournament.id, pair.id), data=pair_payload, format="json")
        assert response.status_code == 200
        assert response.data["weight"] == 560.0
        assert response.data["player1"]["license_number"] == "LIC9990001"

    def test_update_pair_patch_success(self, auth_client, tournament, pair):
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id),
            data={"weight": 999.9},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["weight"] == 999.9

    def test_update_pair_ownership_check(self, auth_client, other_tournament, pair_payload):
        from apps.players.tests.factories import PairFactory
        other_pair = PairFactory(tournament=other_tournament)
        response = auth_client.put(
            pair_detail_url(other_tournament.id, other_pair.id),
            data=pair_payload,
            format="json",
        )
        assert response.status_code == 404

    def test_update_pair_player_already_in_tournament(self, auth_client, tournament):
        from apps.players.tests.factories import PairFactory
        pair_a = PairFactory(tournament=tournament)
        pair_b = PairFactory(tournament=tournament)

        # Try to update pair_b's player1 to use pair_a's player1 license
        payload = {
            "player1": {
                "last_name": pair_a.player1.last_name,
                "first_name": pair_a.player1.first_name,
                "license_number": pair_a.player1.license_number,
                "phone": pair_a.player1.phone,
                "ranking": pair_a.player1.ranking,
            },
            "player2": {
                "last_name": pair_b.player2.last_name,
                "first_name": pair_b.player2.first_name,
                "license_number": pair_b.player2.license_number,
                "phone": pair_b.player2.phone,
                "ranking": pair_b.player2.ranking,
            },
            "weight": 500.0,
        }
        response = auth_client.put(
            pair_detail_url(tournament.id, pair_b.id),
            data=payload,
            format="json",
        )
        assert response.status_code == 400

    def test_update_pair_returns_409_when_tournament_started(self, auth_client, tournament, pair, pair_payload):
        tournament.status = Tournament.Status.STARTED
        tournament.save()
        response = auth_client.put(
            pair_detail_url(tournament.id, pair.id), data=pair_payload, format="json"
        )
        assert response.status_code == 409
        pair.refresh_from_db()
        assert pair.weight != pair_payload["weight"]

    def test_update_pair_returns_409_when_tournament_finished(self, auth_client, tournament, pair, pair_payload):
        tournament.status = Tournament.Status.FINISHED
        tournament.save()
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id),
            data={"weight": 999.9},
            format="json",
        )
        assert response.status_code == 409
        pair.refresh_from_db()
        assert pair.weight != 999.9


# ---------------------------------------------------------------------------
# TestDeletePair
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeletePair:
    def test_delete_pair_requires_auth(self, tournament, pair):
        client = APIClient()
        response = client.delete(pair_detail_url(tournament.id, pair.id))
        assert response.status_code == 401

    def test_delete_pair_success(self, auth_client, tournament, pair):
        response = auth_client.delete(pair_detail_url(tournament.id, pair.id))
        assert response.status_code == 204
        from apps.players.models import Pair
        assert not Pair.objects.filter(id=pair.id).exists()

    def test_delete_pair_not_found(self, auth_client, tournament):
        response = auth_client.delete(pair_detail_url(tournament.id, 99999))
        assert response.status_code == 404

    def test_delete_pair_ownership_check(self, auth_client, other_tournament):
        from apps.players.tests.factories import PairFactory
        other_pair = PairFactory(tournament=other_tournament)
        response = auth_client.delete(pair_detail_url(other_tournament.id, other_pair.id))
        assert response.status_code == 404

    def test_delete_pair_returns_409_when_tournament_started(self, auth_client, tournament, pair):
        from apps.players.models import Pair
        tournament.status = Tournament.Status.STARTED
        tournament.save()
        response = auth_client.delete(pair_detail_url(tournament.id, pair.id))
        assert response.status_code == 409
        assert Pair.objects.filter(id=pair.id).exists()

    def test_delete_pair_returns_409_when_tournament_finished(self, auth_client, tournament, pair):
        from apps.players.models import Pair
        tournament.status = Tournament.Status.FINISHED
        tournament.save()
        response = auth_client.delete(pair_detail_url(tournament.id, pair.id))
        assert response.status_code == 409
        assert Pair.objects.filter(id=pair.id).exists()

