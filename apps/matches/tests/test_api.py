import pytest
from rest_framework.test import APIClient

from apps.matches.models import Bracket, Match
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory


def _bracket_url(tournament_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/bracket/"


def _count_matches(node: dict | None) -> int:
    if node is None:
        return 0
    return 1 + _count_matches(node.get("child1")) + _count_matches(node.get("child2"))


def _collect_rounds(node: dict | None, result: list | None = None) -> list[str]:
    if result is None:
        result = []
    if node is None:
        return result
    result.append(node["round"])
    _collect_rounds(node.get("child1"), result)
    _collect_rounds(node.get("child2"), result)
    return result


def _collect_match_numbers_by_round(
    node: dict | None, result: dict | None = None
) -> dict:
    if result is None:
        result = {}
    if node is None:
        return result
    round_name = node["round"]
    result.setdefault(round_name, []).append(node["match_number"])
    _collect_match_numbers_by_round(node.get("child1"), result)
    _collect_match_numbers_by_round(node.get("child2"), result)
    return result


@pytest.mark.django_db
class TestBracketCreate:
    def test_creates_bracket_dimension_8(self, authenticated_client, tournament):
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["dimension"] == 8
        assert data["nb_top_seeds"] == 2
        root = data["root_match"]
        assert root["round"] == "FINALE"
        assert root["match_number"] == 1
        assert _count_matches(root) == 7  # N - 1

    def test_tree_structure_dimension_8(self, authenticated_client, tournament):
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        root = resp.json()["root_match"]

        sf1 = root["child1"]
        sf2 = root["child2"]
        assert sf1["round"] == "DEMIE_FINALE"
        assert sf2["round"] == "DEMIE_FINALE"
        assert sf1["match_number"] == 1
        assert sf2["match_number"] == 2

        qf_matches = [sf1["child1"], sf1["child2"], sf2["child1"], sf2["child2"]]
        for i, qf in enumerate(qf_matches, start=1):
            assert qf["round"] == "QUART_DE_FINALE"
            assert qf["match_number"] == i
            assert qf["child1"] is None
            assert qf["child2"] is None

    def test_pairs_are_null_at_creation(self, authenticated_client, tournament):
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        root = resp.json()["root_match"]
        assert root["pair1"] is None
        assert root["pair2"] is None
        assert root["child1"]["pair1"] is None

    def test_placement_flags_default_at_creation(
        self, authenticated_client, tournament
    ):
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        root = resp.json()["root_match"]
        for m in _walk_nodes(root):
            assert m["disabled"] is False
            assert m["pair1_can_be_placed"] is True
            assert m["pair2_can_be_placed"] is True

    def test_game_format_inherits_from_tournament(self, authenticated_client, user):
        t = TournamentFactory(owner=user, game_format="A1")
        resp = authenticated_client.post(
            _bracket_url(t.pk), {"dimension": 8, "nb_top_seeds": 2}, format="json"
        )
        assert resp.status_code == 201
        root = resp.json()["root_match"]
        assert all(m["game_format"] == "A1" for m in _walk_nodes(root))

    def test_empty_game_format_when_tournament_has_none(
        self, authenticated_client, user
    ):
        t = TournamentFactory(owner=user, game_format="")
        resp = authenticated_client.post(
            _bracket_url(t.pk), {"dimension": 8, "nb_top_seeds": 2}, format="json"
        )
        assert resp.status_code == 201
        root = resp.json()["root_match"]
        assert root["game_format"] == ""

    @pytest.mark.parametrize(
        "dimension,expected_matches", [(8, 7), (16, 15), (32, 31), (64, 63)]
    )
    def test_all_dimensions_produce_correct_match_count(
        self, authenticated_client, user, dimension, expected_matches
    ):
        t = TournamentFactory(owner=user)
        nb_top_seeds = dimension // 8
        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {"dimension": dimension, "nb_top_seeds": nb_top_seeds},
            format="json",
        )
        assert resp.status_code == 201
        root = resp.json()["root_match"]
        assert _count_matches(root) == expected_matches

    def test_dimension_16_rounds(self, authenticated_client, user):
        t = TournamentFactory(owner=user)
        resp = authenticated_client.post(
            _bracket_url(t.pk), {"dimension": 16, "nb_top_seeds": 2}, format="json"
        )
        root = resp.json()["root_match"]
        rounds = _collect_rounds(root)
        assert rounds.count("FINALE") == 1
        assert rounds.count("DEMIE_FINALE") == 2
        assert rounds.count("QUART_DE_FINALE") == 4
        assert rounds.count("HUITIEME_DE_FINALE") == 8

    def test_match_numbers_are_sequential_per_round(self, authenticated_client, user):
        t = TournamentFactory(owner=user)
        resp = authenticated_client.post(
            _bracket_url(t.pk), {"dimension": 16, "nb_top_seeds": 4}, format="json"
        )
        by_round = _collect_match_numbers_by_round(resp.json()["root_match"])
        assert sorted(by_round["FINALE"]) == [1]
        assert sorted(by_round["DEMIE_FINALE"]) == [1, 2]
        assert sorted(by_round["QUART_DE_FINALE"]) == [1, 2, 3, 4]
        assert sorted(by_round["HUITIEME_DE_FINALE"]) == list(range(1, 9))

    def test_409_if_bracket_exists(self, authenticated_client, tournament):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        assert resp.status_code == 409

    def test_400_invalid_dimension(self, authenticated_client, tournament):
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 12, "nb_top_seeds": 2},
            format="json",
        )
        assert resp.status_code == 400

    def test_400_dimension_4_not_allowed(self, authenticated_client, tournament):
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 4, "nb_top_seeds": 1},
            format="json",
        )
        assert resp.status_code == 400

    def test_400_nb_top_seeds_too_small(self, authenticated_client, tournament):
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 16, "nb_top_seeds": 1},
            format="json",
        )
        assert resp.status_code == 400

    def test_400_nb_top_seeds_too_large(self, authenticated_client, tournament):
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 16, "nb_top_seeds": 9},
            format="json",
        )
        assert resp.status_code == 400

    def test_400_nb_top_seeds_boundary_valid(self, authenticated_client, user):
        t = TournamentFactory(owner=user)
        resp = authenticated_client.post(
            _bracket_url(t.pk), {"dimension": 16, "nb_top_seeds": 2}, format="json"
        )
        assert resp.status_code == 201

        t2 = TournamentFactory(owner=user)
        resp = authenticated_client.post(
            _bracket_url(t2.pk), {"dimension": 16, "nb_top_seeds": 8}, format="json"
        )
        assert resp.status_code == 201

    def test_401_unauthenticated(self, client, tournament):
        resp = client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        assert resp.status_code == 401

    def test_404_non_owner(self, user, tournament):
        other = UserFactory()
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        resp = other_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        assert resp.status_code == 404

    def test_bracket_saved_to_db(self, authenticated_client, tournament):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        assert Bracket.objects.filter(tournament=tournament).count() == 1
        assert Match.objects.filter(bracket__tournament=tournament).count() == 7


@pytest.mark.django_db
class TestBracketRetrieve:
    def test_get_existing_bracket(self, authenticated_client, tournament):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        resp = authenticated_client.get(_bracket_url(tournament.pk))
        assert resp.status_code == 200
        data = resp.json()
        assert data["dimension"] == 8
        assert data["root_match"]["round"] == "FINALE"
        assert _count_matches(data["root_match"]) == 7

    def test_404_no_bracket(self, authenticated_client, tournament):
        resp = authenticated_client.get(_bracket_url(tournament.pk))
        assert resp.status_code == 404

    def test_401_unauthenticated(self, client, tournament):
        resp = client.get(_bracket_url(tournament.pk))
        assert resp.status_code == 401

    def test_404_non_owner_get(self, tournament):
        other = UserFactory()
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        resp = other_client.get(_bracket_url(tournament.pk))
        assert resp.status_code == 404


@pytest.mark.django_db
class TestBracketDelete:
    def test_returns_204(self, authenticated_client, tournament):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        resp = authenticated_client.delete(_bracket_url(tournament.pk))
        assert resp.status_code == 204

    def test_deletes_bracket_from_db(self, authenticated_client, tournament):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        authenticated_client.delete(_bracket_url(tournament.pk))
        assert Bracket.objects.filter(tournament=tournament).count() == 0

    def test_deletes_all_matches_from_db(self, authenticated_client, tournament):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        authenticated_client.delete(_bracket_url(tournament.pk))
        assert Match.objects.filter(bracket__tournament=tournament).count() == 0

    def test_404_no_bracket(self, authenticated_client, tournament):
        resp = authenticated_client.delete(_bracket_url(tournament.pk))
        assert resp.status_code == 404

    def test_401_unauthenticated(self, client, tournament):
        resp = client.delete(_bracket_url(tournament.pk))
        assert resp.status_code == 401

    def test_404_non_owner(self, authenticated_client, tournament):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        other_client = APIClient()
        other_client.force_authenticate(user=UserFactory())
        resp = other_client.delete(_bracket_url(tournament.pk))
        assert resp.status_code == 404

    def test_can_regenerate_after_deletion(self, authenticated_client, tournament):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        authenticated_client.delete(_bracket_url(tournament.pk))
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 16, "nb_top_seeds": 4},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.json()["dimension"] == 16

    def test_409_when_tournament_finished(self, authenticated_client, tournament):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        tournament.status = Tournament.Status.FINISHED
        tournament.save()

        resp = authenticated_client.delete(_bracket_url(tournament.pk))

        assert resp.status_code == 409
        assert Bracket.objects.filter(tournament=tournament).count() == 1
        assert Match.objects.filter(bracket__tournament=tournament).count() > 0

    def test_returns_204_and_reverts_to_set_when_tournament_started(
        self, authenticated_client, tournament
    ):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        tournament.status = Tournament.Status.STARTED
        tournament.save()

        resp = authenticated_client.delete(_bracket_url(tournament.pk))

        assert resp.status_code == 204
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

    def test_status_stays_draft_when_deleted_from_draft(
        self, authenticated_client, tournament
    ):
        """The SET-revert must NOT fire outside of STARTED."""
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        assert tournament.status == Tournament.Status.DRAFT

        resp = authenticated_client.delete(_bracket_url(tournament.pk))

        assert resp.status_code == 204
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_can_regenerate_after_deletion_from_started(
        self, authenticated_client, tournament
    ):
        authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, "nb_top_seeds": 2},
            format="json",
        )
        tournament.status = Tournament.Status.STARTED
        tournament.save()

        authenticated_client.delete(_bracket_url(tournament.pk))
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 16, "nb_top_seeds": 4},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.json()["dimension"] == 16


def _walk_nodes(node: dict | None):
    if node is None:
        return
    yield node
    yield from _walk_nodes(node.get("child1"))
    yield from _walk_nodes(node.get("child2"))
