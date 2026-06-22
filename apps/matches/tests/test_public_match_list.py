import pytest
from rest_framework.test import APIClient

from apps.matches.models import Bracket, Match
from apps.players.tests.factories import PairFactory
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

EXPECTED_FIELDS = {
    "round",
    "round_display",
    "match_number",
    "order",
    "pair1",
    "pair2",
    "winner",
    "game_format",
    "score",
    "status",
    "status_display",
    "started_at",
    "finished_at",
    "estimated_start_at",
}

EXPECTED_PLAYER_FIELDS = {"first_name", "last_name", "ranking", "club"}
EXCLUDED_PLAYER_FIELDS = {"id", "license_number", "phone", "email", "birth_date"}
EXPECTED_PAIR_FIELDS = {"player1", "player2", "weight"}
EXCLUDED_PAIR_FIELDS = {"id", "created_at", "updated_at"}


def _score_url(tournament_id: int, match_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/matches/{match_id}/score/"


def _public_list_url(code: str) -> str:
    return f"/api/v1/public/tournaments/{code}/matches/"


def _zero_seeding() -> dict:
    return {
        "nb_pair_round_64": 0,
        "nb_pair_round_32": 0,
        "nb_pair_round_16": 0,
        "nb_pair_round_8": 0,
        "nb_pair_round_4": 0,
    }


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def authenticated_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def tournament(user):
    return TournamentFactory(owner=user, game_format="B1")


@pytest.fixture
def bracket(authenticated_client, tournament):
    authenticated_client.post(
        f"/api/v1/tournaments/{tournament.pk}/bracket/",
        {"dimension": 8, **_zero_seeding()},
        format="json",
    )
    return Bracket.objects.get(tournament=tournament)


@pytest.mark.django_db
class TestPublicMatchListHappyPath:
    def test_returns_200(self, api_client, tournament, bracket):
        resp = api_client.get(_public_list_url(tournament.public_code))
        assert resp.status_code == 200

    def test_returns_all_matches_ordered_by_order_field(
        self, api_client, tournament, bracket
    ):
        resp = api_client.get(_public_list_url(tournament.public_code))

        expected_orders = list(
            Match.objects.filter(bracket=bracket)
            .order_by("order")
            .values_list("order", flat=True)
        )
        actual_orders = [m["order"] for m in resp.json()]
        assert actual_orders == expected_orders

    def test_response_is_a_plain_array_not_paginated(
        self, api_client, tournament, bracket
    ):
        resp = api_client.get(_public_list_url(tournament.public_code))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_match_payload_has_exact_field_set_and_no_id(
        self, api_client, tournament, bracket
    ):
        resp = api_client.get(_public_list_url(tournament.public_code))
        payload = resp.json()[0]
        assert set(payload.keys()) == EXPECTED_FIELDS
        assert "id" not in payload

    def test_empty_array_when_no_bracket_generated_yet(self, api_client, tournament):
        resp = api_client.get(_public_list_url(tournament.public_code))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_disabled_matches_are_excluded(self, api_client, tournament, bracket):
        match = Match.objects.filter(bracket=bracket).first()
        match.disabled = True
        match.save()

        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        returned_match_numbers = {(m["round"], m["match_number"]) for m in resp.json()}
        assert (match.round, match.match_number) not in returned_match_numbers


@pytest.mark.django_db
class TestPublicMatchListStatusFilter:
    def test_filter_by_single_status(self, api_client, tournament, bracket):
        match = Match.objects.filter(bracket=bracket).first()
        match.status = Match.Status.STARTED
        match.save()

        resp = api_client.get(
            _public_list_url(tournament.public_code), {"status": "STARTED"}
        )

        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["status"] == "STARTED"

    def test_filter_by_multiple_statuses_via_repeated_param(
        self, api_client, tournament, bracket
    ):
        matches = list(Match.objects.filter(bracket=bracket).order_by("order"))
        started_match = matches[0]
        started_match.status = Match.Status.STARTED
        started_match.save()

        finished_match = matches[1]
        finished_match.status = Match.Status.FINISHED
        finished_match.score = "6-4 6-3"
        finished_match.save()

        url = (
            f"{_public_list_url(tournament.public_code)}?status=STARTED&status=FINISHED"
        )
        resp = api_client.get(url)

        assert resp.status_code == 200
        statuses = {m["status"] for m in resp.json()}
        assert statuses == {"STARTED", "FINISHED"}

    def test_no_status_filter_returns_all_statuses(
        self, api_client, tournament, bracket
    ):
        resp = api_client.get(_public_list_url(tournament.public_code))
        assert resp.status_code == 200
        expected_count = Match.objects.filter(bracket=bracket, disabled=False).count()
        assert len(resp.json()) == expected_count


@pytest.mark.django_db
class TestPublicMatchListAuth:
    def test_no_auth_required(self, api_client, tournament, bracket):
        resp = api_client.get(_public_list_url(tournament.public_code))
        assert resp.status_code == 200

    def test_unknown_code_returns_404(self, api_client):
        resp = api_client.get(_public_list_url("ZZZZZZZZ"))
        assert resp.status_code == 404

    def test_post_returns_405(self, api_client, tournament, bracket):
        resp = api_client.post(_public_list_url(tournament.public_code), {})
        assert resp.status_code == 405


@pytest.mark.django_db
class TestPublicMatchListEstimatedStartAt:
    def test_upcoming_match_has_non_null_estimate_when_finished_match_exists(
        self, api_client, tournament, bracket
    ):
        tournament.estimated_match_duration = 45
        tournament.save()
        resp = api_client.get(_public_list_url(tournament.public_code))
        assert resp.status_code == 200
        upcoming_payloads = [m for m in resp.json() if m["status"] == "UPCOMING"]
        assert upcoming_payloads

    def test_started_and_finished_matches_have_null_estimate(
        self, api_client, tournament, bracket
    ):
        tournament.estimated_match_duration = 45
        tournament.save()
        matches = list(Match.objects.filter(bracket=bracket).order_by("order"))
        started_match = matches[0]
        started_match.status = Match.Status.STARTED
        started_match.save()
        finished_match = matches[1]
        finished_match.status = Match.Status.FINISHED
        finished_match.score = "6/4 6/4"
        finished_match.save()

        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        for m in resp.json():
            if m["status"] in ("STARTED", "FINISHED"):
                assert m["estimated_start_at"] is None


@pytest.mark.django_db
class TestPublicMatchListNestedPairs:
    def test_pair1_and_pair2_are_null_when_not_yet_placed(
        self, api_client, tournament, bracket
    ):
        # `bracket` fixture is generated with zero seeding and no
        # registered pairs, so no match has pair1/pair2 placed yet.
        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        payloads = resp.json()
        assert payloads
        for match in payloads:
            assert match["pair1"] is None
            assert match["pair2"] is None

    def test_winner_is_null_before_a_score_is_entered(
        self, api_client, tournament, bracket
    ):
        match = Match.objects.filter(bracket=bracket).first()

        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        payload = next(
            m
            for m in resp.json()
            if m["round"] == match.round and m["match_number"] == match.match_number
        )
        assert payload["winner"] is None

    def test_pair_payload_has_exact_field_set(
        self, api_client, authenticated_client, tournament, bracket
    ):
        match = Match.objects.filter(bracket=bracket).first()
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match.pair1 = pair1
        match.pair2 = pair2
        match.save(update_fields=["pair1", "pair2", "updated_at"])

        authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4 6/4", "winner_id": pair1.pk},
            format="json",
        )

        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        payload = next(
            m
            for m in resp.json()
            if m["round"] == match.round and m["match_number"] == match.match_number
        )

        for pair_payload in (payload["pair1"], payload["pair2"], payload["winner"]):
            assert set(pair_payload.keys()) == EXPECTED_PAIR_FIELDS
            assert EXCLUDED_PAIR_FIELDS.isdisjoint(pair_payload.keys())

    def test_player_payload_has_exact_field_set_and_excludes_pii(
        self, api_client, authenticated_client, tournament, bracket
    ):
        match = Match.objects.filter(bracket=bracket).first()
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match.pair1 = pair1
        match.pair2 = pair2
        match.save(update_fields=["pair1", "pair2", "updated_at"])

        authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4 6/4", "winner_id": pair1.pk},
            format="json",
        )

        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        payload = next(
            m
            for m in resp.json()
            if m["round"] == match.round and m["match_number"] == match.match_number
        )

        for pair_payload in (payload["pair1"], payload["pair2"], payload["winner"]):
            for player_payload in (pair_payload["player1"], pair_payload["player2"]):
                assert set(player_payload.keys()) == EXPECTED_PLAYER_FIELDS
                for excluded_field in EXCLUDED_PLAYER_FIELDS:
                    assert excluded_field not in player_payload

    def test_winner_is_fully_nested_pair_once_score_entered(
        self, api_client, authenticated_client, tournament, bracket
    ):
        match = Match.objects.filter(bracket=bracket).first()
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match.pair1 = pair1
        match.pair2 = pair2
        match.save(update_fields=["pair1", "pair2", "updated_at"])

        authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4 6/4", "winner_id": pair1.pk},
            format="json",
        )

        resp = api_client.get(_public_list_url(tournament.public_code))

        assert resp.status_code == 200
        payload = next(
            m
            for m in resp.json()
            if m["round"] == match.round and m["match_number"] == match.match_number
        )

        assert payload["winner"] is not None
        assert payload["winner"]["player1"]["first_name"] == pair1.player1.first_name
        assert payload["winner"]["player1"]["last_name"] == pair1.player1.last_name
        assert payload["winner"]["player2"]["first_name"] == pair1.player2.first_name
        assert payload["winner"]["player2"]["last_name"] == pair1.player2.last_name
