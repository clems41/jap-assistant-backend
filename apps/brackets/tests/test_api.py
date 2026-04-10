import pytest
from rest_framework.test import APIClient

from apps.brackets.models import BracketSlot, BracketState
from apps.players.tests.factories import PairFactory
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

from .factories import BracketSlotFactory, BracketStateFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BRACKET_URL = "/api/v1/tournaments/{tournament_id}/bracket/"


def bracket_url(tournament_id: int) -> str:
    return BRACKET_URL.format(tournament_id=tournament_id)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def tournament(user):
    return TournamentFactory(owner=user)


@pytest.fixture
def other_tournament():
    return TournamentFactory()


# ---------------------------------------------------------------------------
# GET /api/v1/brackets/<tournament_id>/
# ---------------------------------------------------------------------------


class TestGetBracket:
    @pytest.mark.django_db
    def test_unauthenticated_returns_401(self):
        tournament = TournamentFactory()
        response = APIClient().get(bracket_url(tournament.pk))
        assert response.status_code == 401

    @pytest.mark.django_db
    def test_other_owner_returns_404(self, client, other_tournament):
        response = client.get(bracket_url(other_tournament.pk))
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_nonexistent_tournament_returns_404(self, client):
        response = client.get(bracket_url(99999))
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_no_bracket_returns_404(self, client, tournament):
        response = client.get(bracket_url(tournament.pk))
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_returns_bracket_with_empty_slots(self, client, tournament):
        BracketStateFactory(tournament=tournament, dimension=16, nb_top_seeds=2)
        response = client.get(bracket_url(tournament.pk))
        assert response.status_code == 200
        data = response.json()
        assert data["dimension"] == 16
        assert data["nb_top_seeds"] == 2
        assert data["tournament_id"] == tournament.pk
        assert data["slots"] == []

    @pytest.mark.django_db
    def test_returns_bracket_with_slots(self, client, tournament):
        bracket = BracketStateFactory(tournament=tournament, dimension=16, nb_top_seeds=0)
        pair = PairFactory(tournament=tournament)
        BracketSlotFactory(bracket_state=bracket, slot_title="R16 #1", pair=pair)

        response = client.get(bracket_url(tournament.pk))
        assert response.status_code == 200
        data = response.json()
        assert len(data["slots"]) == 1
        slot = data["slots"][0]
        assert slot["slot_title"] == "R16 #1"
        assert slot["pair"]["id"] == pair.pk
        assert slot["pair"]["player1"]["id"] == pair.player1.pk
        assert slot["pair"]["player1"]["last_name"] == pair.player1.last_name
        assert slot["pair"]["player1"]["first_name"] == pair.player1.first_name
        assert slot["pair"]["player1"]["license_number"] == pair.player1.license_number
        assert slot["pair"]["player2"]["id"] == pair.player2.pk
        assert "weight" in slot["pair"]

    @pytest.mark.django_db
    def test_slot_includes_score_field(self, client, tournament):
        bracket = BracketStateFactory(tournament=tournament)
        pair = PairFactory(tournament=tournament)
        BracketSlotFactory(bracket_state=bracket, slot_title="R16 #1", pair=pair)
        response = client.get(bracket_url(tournament.pk))
        assert response.status_code == 200
        assert "score" in response.json()["slots"][0]
        assert response.json()["slots"][0]["score"] is None

    @pytest.mark.django_db
    def test_slot_score_returned_when_set(self, client, tournament):
        bracket = BracketStateFactory(tournament=tournament)
        pair = PairFactory(tournament=tournament)
        BracketSlotFactory(bracket_state=bracket, slot_title="QF #1", pair=pair, score="6/3 6/4")
        response = client.get(bracket_url(tournament.pk))
        assert response.status_code == 200
        assert response.json()["slots"][0]["score"] == "6/3 6/4"

    @pytest.mark.django_db
    def test_response_includes_id(self, client, tournament):
        bracket = BracketStateFactory(tournament=tournament)
        response = client.get(bracket_url(tournament.pk))
        assert response.status_code == 200
        assert response.json()["id"] == bracket.pk


# ---------------------------------------------------------------------------
# PUT /api/v1/brackets/<tournament_id>/
# ---------------------------------------------------------------------------


class TestPutBracket:
    @pytest.mark.django_db
    def test_unauthenticated_returns_401(self):
        tournament = TournamentFactory()
        response = APIClient().put(bracket_url(tournament.pk), {}, format="json")
        assert response.status_code == 401

    @pytest.mark.django_db
    def test_other_owner_returns_404(self, client, other_tournament):
        payload = {"dimension": 16, "nb_top_seeds": 0, "slots": []}
        response = client.put(bracket_url(other_tournament.pk), payload, format="json")
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_nonexistent_tournament_returns_404(self, client):
        payload = {"dimension": 16, "nb_top_seeds": 0, "slots": []}
        response = client.put(bracket_url(99999), payload, format="json")
        assert response.status_code == 404

    @pytest.mark.django_db
    def test_invalid_dimension_returns_400(self, client, tournament):
        payload = {"dimension": 7, "nb_top_seeds": 0, "slots": []}
        response = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_negative_nb_top_seeds_returns_400(self, client, tournament):
        payload = {"dimension": 16, "nb_top_seeds": -1, "slots": []}
        response = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_pair_from_other_tournament_returns_400(self, client, tournament):
        other_pair = PairFactory()
        payload = {
            "dimension": 16,
            "nb_top_seeds": 0,
            "slots": [{"slot_title": "R16 #1", "pair_id": other_pair.pk}],
        }
        response = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_duplicate_pair_id_returns_400(self, client, tournament):
        pair = PairFactory(tournament=tournament)
        payload = {
            "dimension": 16,
            "nb_top_seeds": 0,
            "slots": [
                {"slot_title": "R16 #1", "pair_id": pair.pk},
                {"slot_title": "R16 #3", "pair_id": pair.pk},
            ],
        }
        response = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_duplicate_slot_title_returns_400(self, client, tournament):
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        payload = {
            "dimension": 16,
            "nb_top_seeds": 0,
            "slots": [
                {"slot_title": "R16 #1", "pair_id": pair1.pk},
                {"slot_title": "R16 #1", "pair_id": pair2.pk},
            ],
        }
        response = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_creates_bracket_and_returns_200(self, client, tournament):
        pair = PairFactory(tournament=tournament)
        payload = {
            "dimension": 16,
            "nb_top_seeds": 2,
            "slots": [{"slot_title": "R16 #1", "pair_id": pair.pk}],
        }
        response = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response.status_code == 200
        assert BracketState.objects.filter(tournament=tournament).exists()
        assert BracketSlot.objects.filter(bracket_state__tournament=tournament).count() == 1
        data = response.json()
        assert data["dimension"] == 16
        assert data["nb_top_seeds"] == 2
        assert len(data["slots"]) == 1
        assert data["slots"][0]["slot_title"] == "R16 #1"

    @pytest.mark.django_db
    def test_empty_slots_creates_bracket(self, client, tournament):
        payload = {"dimension": 8, "nb_top_seeds": 0, "slots": []}
        response = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response.status_code == 200
        assert BracketState.objects.filter(tournament=tournament).exists()

    @pytest.mark.django_db
    def test_overwrites_existing_bracket(self, client, tournament):
        bracket = BracketStateFactory(tournament=tournament, dimension=16, nb_top_seeds=0)
        old_pair = PairFactory(tournament=tournament)
        BracketSlotFactory(bracket_state=bracket, slot_title="R16 #1", pair=old_pair)

        new_pair = PairFactory(tournament=tournament)
        payload = {
            "dimension": 32,
            "nb_top_seeds": 4,
            "slots": [{"slot_title": "R32 #1", "pair_id": new_pair.pk}],
        }
        response = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response.status_code == 200
        data = response.json()
        assert data["dimension"] == 32
        assert data["nb_top_seeds"] == 4
        assert len(data["slots"]) == 1
        assert data["slots"][0]["slot_title"] == "R32 #1"
        assert BracketSlot.objects.filter(bracket_state__tournament=tournament).count() == 1

    @pytest.mark.django_db
    def test_put_slot_with_score_saves_correctly(self, client, tournament):
        pair = PairFactory(tournament=tournament)
        payload = {
            "dimension": 16,
            "nb_top_seeds": 0,
            "slots": [{"slot_title": "QF #1", "pair_id": pair.pk, "score": "6/3 6/4"}],
        }
        response = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response.status_code == 200
        slot = response.json()["slots"][0]
        assert slot["score"] == "6/3 6/4"
        from apps.brackets.models import BracketSlot
        assert BracketSlot.objects.get(slot_title="QF #1").score == "6/3 6/4"

    @pytest.mark.django_db
    def test_put_slot_without_score_has_null_score(self, client, tournament):
        pair = PairFactory(tournament=tournament)
        payload = {
            "dimension": 16,
            "nb_top_seeds": 0,
            "slots": [{"slot_title": "QF #1", "pair_id": pair.pk}],
        }
        response = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response.status_code == 200
        assert response.json()["slots"][0]["score"] is None

    @pytest.mark.django_db
    def test_idempotent(self, client, tournament):
        pair = PairFactory(tournament=tournament)
        payload = {
            "dimension": 16,
            "nb_top_seeds": 0,
            "slots": [{"slot_title": "R16 #1", "pair_id": pair.pk}],
        }
        response1 = client.put(bracket_url(tournament.pk), payload, format="json")
        response2 = client.put(bracket_url(tournament.pk), payload, format="json")
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert BracketState.objects.filter(tournament=tournament).count() == 1
        assert BracketSlot.objects.filter(bracket_state__tournament=tournament).count() == 1
