import pytest
from rest_framework.test import APIClient

from apps.matches.models import Bracket, Match, Round
from apps.players.tests.factories import PairFactory
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory


def placement_url(tournament_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/bracket/placement/"


@pytest.fixture
def bracket(authenticated_client, tournament):
    authenticated_client.post(
        f"/api/v1/tournaments/{tournament.pk}/bracket/",
        {"dimension": 8, "nb_top_seeds": 2},
        format="json",
    )
    return Bracket.objects.get(tournament=tournament)


@pytest.fixture
def leaf_matches(bracket):
    return list(
        Match.objects.filter(bracket=bracket, child1__isnull=True).order_by("match_number")
    )


@pytest.fixture
def second_round_matches(bracket):
    return list(
        Match.objects.filter(bracket=bracket, round=Round.DEMIE_FINALE).order_by("match_number")
    )


@pytest.fixture
def pairs(tournament):
    return [PairFactory(tournament=tournament) for _ in range(8)]


@pytest.mark.django_db
class TestBracketPlacement:
    def test_partial_placement_saves_pairs(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        payload = {
            "placements": [
                {"match_id": leaf_matches[0].pk, "pair1_id": pairs[0].pk, "pair2_id": pairs[1].pk},
                {"match_id": leaf_matches[1].pk, "pair1_id": pairs[2].pk, "pair2_id": pairs[3].pk},
            ]
        }
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 200

        leaf_matches[0].refresh_from_db()
        leaf_matches[1].refresh_from_db()
        leaf_matches[2].refresh_from_db()

        assert leaf_matches[0].pair1_id == pairs[0].pk
        assert leaf_matches[0].pair2_id == pairs[1].pk
        assert leaf_matches[1].pair1_id == pairs[2].pk
        assert leaf_matches[1].pair2_id == pairs[3].pk
        assert leaf_matches[2].pair1_id is None
        assert leaf_matches[2].pair2_id is None

    def test_top_seed_placed_in_second_round(
        self, authenticated_client, tournament, bracket, second_round_matches, pairs
    ):
        payload = {
            "placements": [
                {
                    "match_id": second_round_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": None,
                },
            ]
        }
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 200

        second_round_matches[0].refresh_from_db()
        assert second_round_matches[0].pair1_id == pairs[0].pk
        assert second_round_matches[0].pair2_id is None

    def test_null_pair_unplaces_existing_pair(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        leaf_matches[0].pair1 = pairs[0]
        leaf_matches[0].save()

        payload = {
            "placements": [
                {"match_id": leaf_matches[0].pk, "pair1_id": None, "pair2_id": None},
            ]
        }
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 200

        leaf_matches[0].refresh_from_db()
        assert leaf_matches[0].pair1_id is None

    def test_response_is_full_bracket(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        payload = {
            "placements": [
                {"match_id": leaf_matches[0].pk, "pair1_id": pairs[0].pk, "pair2_id": pairs[1].pk},
            ]
        }
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 200
        data = resp.json()
        assert "dimension" in data
        assert "root_match" in data
        assert data["root_match"]["round"] == "FINALE"

    def test_400_match_not_in_tournament_bracket(
        self, authenticated_client, tournament, bracket, pairs
    ):
        other_tournament = TournamentFactory(owner=tournament.owner)
        other_bracket = Bracket.objects.create(
            tournament=other_tournament, dimension=8, nb_top_seeds=2
        )
        other_match = Match.objects.create(
            bracket=other_bracket,
            round=Round.QUART_DE_FINALE,
            match_number=1,
        )
        payload = {
            "placements": [
                {"match_id": other_match.pk, "pair1_id": pairs[0].pk, "pair2_id": None},
            ]
        }
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 400

    def test_400_match_already_scored(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        leaf_matches[0].score = "6-4 6-3"
        leaf_matches[0].save()

        payload = {
            "placements": [
                {"match_id": leaf_matches[0].pk, "pair1_id": pairs[0].pk, "pair2_id": pairs[1].pk},
            ]
        }
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 400

    def test_400_pair_not_in_tournament(
        self, authenticated_client, tournament, bracket, leaf_matches
    ):
        other_pair = PairFactory()
        payload = {
            "placements": [
                {"match_id": leaf_matches[0].pk, "pair1_id": other_pair.pk, "pair2_id": None},
            ]
        }
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 400

    def test_400_same_pair_twice_in_request(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        payload = {
            "placements": [
                {"match_id": leaf_matches[0].pk, "pair1_id": pairs[0].pk, "pair2_id": None},
                {"match_id": leaf_matches[1].pk, "pair1_id": pairs[0].pk, "pair2_id": None},
            ]
        }
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 400

    def test_400_pair_already_placed_in_other_match(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        leaf_matches[2].pair1 = pairs[0]
        leaf_matches[2].save()

        payload = {
            "placements": [
                {"match_id": leaf_matches[0].pk, "pair1_id": pairs[0].pk, "pair2_id": None},
            ]
        }
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 400

    def test_400_pair1_same_as_pair2(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": pairs[0].pk,
                },
            ]
        }
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 400

    def test_401_unauthenticated(self, tournament, bracket, leaf_matches, pairs):
        anon = APIClient()
        payload = {
            "placements": [
                {"match_id": leaf_matches[0].pk, "pair1_id": pairs[0].pk, "pair2_id": None},
            ]
        }
        resp = anon.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 401

    def test_404_non_owner(self, tournament, bracket, leaf_matches, pairs):
        other = UserFactory()
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        payload = {
            "placements": [
                {"match_id": leaf_matches[0].pk, "pair1_id": pairs[0].pk, "pair2_id": None},
            ]
        }
        resp = other_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 404

    def test_404_no_bracket(self, authenticated_client, tournament):
        payload = {"placements": []}
        resp = authenticated_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 404
