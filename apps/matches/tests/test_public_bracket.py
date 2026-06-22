import pytest
from rest_framework.test import APIClient

from apps.matches.models import Bracket
from apps.players.tests.factories import PairFactory
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

EXCLUDED_MATCH_FIELDS = {"id", "pair1_can_be_placed", "pair2_can_be_placed"}
EXPECTED_MATCH_FIELDS = {
    "round",
    "round_display",
    "match_number",
    "order",
    "pair1",
    "pair2",
    "winner_id",
    "game_format",
    "score",
    "child1",
    "child2",
    "disabled",
    "status",
    "status_display",
    "started_at",
    "finished_at",
}
EXPECTED_CLASSIFICATION_BRACKET_FIELDS = {
    "source_round",
    "source_round_display",
    "start_place",
    "end_place",
    "root_match",
    "children",
}


def _public_bracket_url(code: str) -> str:
    return f"/api/v1/public/tournaments/{code}/bracket/"


def _zero_seeding() -> dict:
    return {
        "nb_pair_round_64": 0,
        "nb_pair_round_32": 0,
        "nb_pair_round_16": 0,
        "nb_pair_round_8": 0,
        "nb_pair_round_4": 0,
    }


def _walk_matches(node):
    """Yield node and all descendant match nodes (child1/child2), recursively."""
    if node is None:
        return
    yield node
    yield from _walk_matches(node.get("child1"))
    yield from _walk_matches(node.get("child2"))


def _walk_classification_brackets(bracket):
    """Yield bracket and all descendant classification bracket nodes."""
    yield bracket
    for child in bracket.get("children", []):
        yield from _walk_classification_brackets(child)


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
def bracket_with_classification(authenticated_client, tournament):
    """Dimension 16, 12 pairs, seeding 0/0/8/4/0 (pairs_count=12): same
    worked example as apps/matches/tests/test_classification_brackets.py
    ("pairs_count=12, dimension=16, seeding 0/0/8/4/0"). HUITIEME_DE_FINALE
    has 8 entrants -> 4 real matches -> classification bracket of
    dimension 4 is generated."""
    PairFactory.create_batch(12, tournament=tournament)
    authenticated_client.post(
        f"/api/v1/tournaments/{tournament.pk}/bracket/",
        {
            "dimension": 16,
            "nb_pair_round_64": 0,
            "nb_pair_round_32": 0,
            "nb_pair_round_16": 8,
            "nb_pair_round_8": 4,
            "nb_pair_round_4": 0,
        },
        format="json",
    )
    return Bracket.objects.get(tournament=tournament, parent__isnull=True)


@pytest.fixture
def bracket(authenticated_client, tournament):
    authenticated_client.post(
        f"/api/v1/tournaments/{tournament.pk}/bracket/",
        {"dimension": 8, **_zero_seeding()},
        format="json",
    )
    return Bracket.objects.get(tournament=tournament, parent__isnull=True)


@pytest.mark.django_db
class TestPublicBracketHappyPath:
    def test_returns_200(self, api_client, tournament, bracket):
        resp = api_client.get(_public_bracket_url(tournament.public_code))
        assert resp.status_code == 200

    def test_top_level_keys_are_exactly_root_match_and_classification_brackets(
        self, api_client, tournament, bracket
    ):
        resp = api_client.get(_public_bracket_url(tournament.public_code))
        assert set(resp.json().keys()) == {"root_match", "classification_brackets"}

    def test_root_match_and_descendants_have_no_excluded_fields(
        self, api_client, tournament, bracket
    ):
        resp = api_client.get(_public_bracket_url(tournament.public_code))
        root = resp.json()["root_match"]
        for match in _walk_matches(root):
            assert EXCLUDED_MATCH_FIELDS.isdisjoint(match.keys())
            assert set(match.keys()) == EXPECTED_MATCH_FIELDS

    def test_root_match_and_descendants_keep_disabled_field(
        self, api_client, tournament, bracket
    ):
        resp = api_client.get(_public_bracket_url(tournament.public_code))
        root = resp.json()["root_match"]
        for match in _walk_matches(root):
            assert "disabled" in match

    def test_classification_brackets_have_no_id_or_dimension(
        self, api_client, tournament, bracket_with_classification
    ):
        resp = api_client.get(_public_bracket_url(tournament.public_code))
        classification_brackets = resp.json()["classification_brackets"]
        assert classification_brackets

        for cb in classification_brackets:
            for node in _walk_classification_brackets(cb):
                assert "id" not in node
                assert "dimension" not in node
                assert set(node.keys()) == EXPECTED_CLASSIFICATION_BRACKET_FIELDS

    def test_classification_bracket_root_matches_have_no_excluded_fields(
        self, api_client, tournament, bracket_with_classification
    ):
        resp = api_client.get(_public_bracket_url(tournament.public_code))
        classification_brackets = resp.json()["classification_brackets"]
        assert classification_brackets

        for cb in classification_brackets:
            for node in _walk_classification_brackets(cb):
                for match in _walk_matches(node["root_match"]):
                    assert EXCLUDED_MATCH_FIELDS.isdisjoint(match.keys())


@pytest.mark.django_db
class TestPublicBracketAuthAndErrors:
    def test_no_auth_required(self, api_client, tournament, bracket):
        resp = api_client.get(_public_bracket_url(tournament.public_code))
        assert resp.status_code == 200

    def test_unknown_code_returns_404(self, api_client):
        resp = api_client.get(_public_bracket_url("ZZZZZZZZ"))
        assert resp.status_code == 404

    def test_no_bracket_generated_yet_returns_404(self, api_client, tournament):
        resp = api_client.get(_public_bracket_url(tournament.public_code))
        assert resp.status_code == 404

    def test_post_returns_405(self, api_client, tournament, bracket):
        resp = api_client.post(_public_bracket_url(tournament.public_code), {})
        assert resp.status_code == 405

    def test_delete_returns_405(self, api_client, tournament, bracket):
        resp = api_client.delete(_public_bracket_url(tournament.public_code))
        assert resp.status_code == 405
