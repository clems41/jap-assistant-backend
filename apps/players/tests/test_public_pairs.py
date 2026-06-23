import pytest
from rest_framework.test import APIClient

from apps.players.tests.factories import PairFactory
from apps.tournaments.tests.factories import TournamentFactory

EXPECTED_PLAYER_FIELDS = {"first_name", "last_name", "ranking", "club"}
EXCLUDED_PLAYER_FIELDS = {"id", "license_number", "phone", "email", "birth_date"}
EXPECTED_PAIR_FIELDS = {"player1", "player2", "weight"}
EXCLUDED_PAIR_FIELDS = {"id", "created_at", "updated_at"}


def _public_list_url(code: str) -> str:
    return f"/api/v1/public/tournaments/{code}/pairs/"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def tournament():
    return TournamentFactory()


@pytest.mark.django_db
class TestPublicPairListHappyPath:
    def test_returns_200(self, api_client, tournament):
        PairFactory(tournament=tournament)
        resp = api_client.get(_public_list_url(tournament.public_code))
        assert resp.status_code == 200

    def test_response_is_a_plain_array_not_paginated(self, api_client, tournament):
        PairFactory(tournament=tournament)
        resp = api_client.get(_public_list_url(tournament.public_code))
        assert resp.status_code == 200
        payload = resp.json()
        assert isinstance(payload, list)
        assert "count" not in payload
        assert "results" not in payload

    def test_returns_all_pairs_of_the_tournament(self, api_client, tournament):
        PairFactory(tournament=tournament)
        PairFactory(tournament=tournament)

        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_excludes_pairs_from_other_tournaments(self, api_client, tournament):
        PairFactory(tournament=tournament)
        other_tournament = TournamentFactory()
        PairFactory(tournament=other_tournament)

        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_empty_array_when_tournament_has_no_pairs(self, api_client, tournament):
        resp = api_client.get(_public_list_url(tournament.public_code))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_pair_payload_has_exact_field_set(self, api_client, tournament):
        PairFactory(tournament=tournament)

        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        payload = resp.json()[0]
        assert set(payload.keys()) == EXPECTED_PAIR_FIELDS
        assert EXCLUDED_PAIR_FIELDS.isdisjoint(payload.keys())

    def test_player_payload_has_exact_field_set_and_excludes_pii(
        self, api_client, tournament
    ):
        PairFactory(tournament=tournament)

        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        payload = resp.json()[0]
        for player_payload in (payload["player1"], payload["player2"]):
            assert set(player_payload.keys()) == EXPECTED_PLAYER_FIELDS
            assert EXCLUDED_PLAYER_FIELDS.isdisjoint(player_payload.keys())


@pytest.mark.django_db
class TestPublicPairListAuth:
    def test_no_auth_required(self, api_client, tournament):
        PairFactory(tournament=tournament)
        resp = api_client.get(_public_list_url(tournament.public_code))
        assert resp.status_code == 200

    def test_unknown_code_returns_404(self, api_client):
        resp = api_client.get(_public_list_url("ZZZZZZZZ"))
        assert resp.status_code == 404

    def test_post_returns_405(self, api_client, tournament):
        resp = api_client.post(_public_list_url(tournament.public_code), {})
        assert resp.status_code == 405
