import pytest

from apps.players.tests.factories import PairFactory
from apps.tournaments.tests.factories import TournamentFactory


def _bracket_url(tournament_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/bracket/"


def _by_start_place(brackets: list[dict]) -> dict[int, dict]:
    return {b["start_place"]: b for b in brackets}


@pytest.mark.django_db
class TestClassificationBracketsGeneration:
    def test_user_worked_example_dimension_32_seeding_0_8_4_4_0(
        self, authenticated_client, user
    ):
        """dimension=32, 16 pairs, seeding 0/8/4/4/0 -> 4 classification brackets:
        dims [4,4,4,2], places (13,16),(9,12),(5,8),(3,4),
        source_round SEIZIEME/HUITIEME/QUART/DEMIE_FINALE respectively.
        """
        t = TournamentFactory(owner=user)
        PairFactory.create_batch(16, tournament=t)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 32,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 8,
                "nb_pair_round_16": 4,
                "nb_pair_round_8": 4,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        assert resp.status_code == 201
        data = resp.json()
        brackets = data["classification_brackets"]
        assert len(brackets) == 4

        by_place = _by_start_place(brackets)

        b_13 = by_place[13]
        assert b_13["dimension"] == 4
        assert b_13["end_place"] == 16
        assert b_13["source_round"] == "SEIZIEME_DE_FINALE"

        b_9 = by_place[9]
        assert b_9["dimension"] == 4
        assert b_9["end_place"] == 12
        assert b_9["source_round"] == "HUITIEME_DE_FINALE"

        b_5 = by_place[5]
        assert b_5["dimension"] == 4
        assert b_5["end_place"] == 8
        assert b_5["source_round"] == "QUART_DE_FINALE"

        b_3 = by_place[3]
        assert b_3["dimension"] == 2
        assert b_3["end_place"] == 4
        assert b_3["source_round"] == "DEMIE_FINALE"

    def test_each_dim4_bracket_cascades_to_exactly_one_dim2_child(
        self, authenticated_client, user
    ):
        """Cascade 1 level: each of the 3 dim=4 classification brackets above
        gets exactly 1 child of dim=2; the dim=2 bracket (#4) has no children.
        """
        t = TournamentFactory(owner=user)
        PairFactory.create_batch(16, tournament=t)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 32,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 8,
                "nb_pair_round_16": 4,
                "nb_pair_round_8": 4,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        brackets = resp.json()["classification_brackets"]
        by_place = _by_start_place(brackets)

        b_13 = by_place[13]
        assert len(b_13["children"]) == 1
        assert b_13["children"][0]["dimension"] == 2
        assert b_13["children"][0]["start_place"] == 15
        assert b_13["children"][0]["end_place"] == 16

        b_9 = by_place[9]
        assert len(b_9["children"]) == 1
        assert b_9["children"][0]["dimension"] == 2
        assert b_9["children"][0]["start_place"] == 11
        assert b_9["children"][0]["end_place"] == 12

        b_5 = by_place[5]
        assert len(b_5["children"]) == 1
        assert b_5["children"][0]["dimension"] == 2
        assert b_5["children"][0]["start_place"] == 7
        assert b_5["children"][0]["end_place"] == 8

        b_3 = by_place[3]
        assert b_3["dimension"] == 2
        assert b_3["children"] == []

    def test_dim4_classification_bracket_tree_structure(
        self, authenticated_client, user
    ):
        """A dim=4 classification bracket's own match tree: root FINALE with
        2 DEMIE_FINALE children (match_number 1/2), no grandchildren -> 3
        matches total (D - 1).
        """
        t = TournamentFactory(owner=user)
        PairFactory.create_batch(16, tournament=t)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 32,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 8,
                "nb_pair_round_16": 4,
                "nb_pair_round_8": 4,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        brackets = resp.json()["classification_brackets"]
        b_13 = _by_start_place(brackets)[13]

        root = b_13["root_match"]
        assert root["round"] == "FINALE"
        assert root["child1"]["round"] == "DEMIE_FINALE"
        assert root["child2"]["round"] == "DEMIE_FINALE"
        match_numbers = sorted(
            [root["child1"]["match_number"], root["child2"]["match_number"]]
        )
        assert match_numbers == [1, 2]
        assert root["child1"]["child1"] is None
        assert root["child1"]["child2"] is None
        assert root["child2"]["child1"] is None
        assert root["child2"]["child2"] is None

    def test_dim2_classification_bracket_root_match_has_no_children(
        self, authenticated_client, user
    ):
        t = TournamentFactory(owner=user)
        PairFactory.create_batch(16, tournament=t)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 32,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 8,
                "nb_pair_round_16": 4,
                "nb_pair_round_8": 4,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        brackets = resp.json()["classification_brackets"]
        b_3 = _by_start_place(brackets)[3]

        root = b_3["root_match"]
        assert root["round"] == "FINALE"
        assert root["child1"] is None
        assert root["child2"] is None

    def test_round_with_zero_real_losers_creates_no_bracket(
        self, authenticated_client, user
    ):
        """pairs_count=12, dimension=32, seeding 0/0/8/4/0: SEIZIEME entering=0
        produces no bracket; only 3 classification_brackets total (HUITIEME,
        QUART, DEMIE_FINALE).
        """
        t = TournamentFactory(owner=user)
        PairFactory.create_batch(12, tournament=t)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 32,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 0,
                "nb_pair_round_16": 8,
                "nb_pair_round_8": 4,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        assert resp.status_code == 201
        brackets = resp.json()["classification_brackets"]
        assert len(brackets) == 3
        source_rounds = {b["source_round"] for b in brackets}
        assert source_rounds == {"HUITIEME_DE_FINALE", "QUART_DE_FINALE", "DEMIE_FINALE"}

        by_place = _by_start_place(brackets)
        assert by_place[9]["dimension"] == 4
        assert by_place[9]["end_place"] == 12
        assert by_place[5]["dimension"] == 4
        assert by_place[5]["end_place"] == 8
        assert by_place[3]["dimension"] == 2
        assert by_place[3]["end_place"] == 4

    def test_depth_2_cascade_dimension_16_seeding_all_at_round_16(
        self, authenticated_client, user
    ):
        """dimension=16, 16 pairs, seeding nb_pair_round_16=16 (rest 0):
        HUITIEME produces a dim=8 bracket (places 9-16). It must have exactly
        2 children: a dim=4 (start_place = 9+4=13) and a dim=2
        (start_place = 9+2=11). The dim=4 child itself has exactly 1 child
        dim=2 (start_place = 13+2=15).
        """
        t = TournamentFactory(owner=user)
        PairFactory.create_batch(16, tournament=t)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 16,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 0,
                "nb_pair_round_16": 16,
                "nb_pair_round_8": 0,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        assert resp.status_code == 201
        brackets = resp.json()["classification_brackets"]
        by_place = _by_start_place(brackets)

        b_9 = by_place[9]
        assert b_9["dimension"] == 8
        assert b_9["end_place"] == 16
        assert b_9["source_round"] == "HUITIEME_DE_FINALE"
        assert len(b_9["children"]) == 2

        children_by_place = _by_start_place(b_9["children"])
        dim4_child = children_by_place[13]
        dim2_child = children_by_place[11]

        assert dim4_child["dimension"] == 4
        assert dim4_child["end_place"] == 16
        assert dim2_child["dimension"] == 2
        assert dim2_child["end_place"] == 12

        assert len(dim4_child["children"]) == 1
        grandchild = dim4_child["children"][0]
        assert grandchild["dimension"] == 2
        assert grandchild["start_place"] == 15
        assert grandchild["end_place"] == 16
        assert grandchild["children"] == []

        assert dim2_child["children"] == []


@pytest.mark.django_db
class TestBracketGenerateStructuralCapValidation:
    def test_400_round_exceeds_structural_cap(self, authenticated_client, user):
        """64 pairs, seeding 32/16/8/4/4: HUITIEME entering=16+8=24 ->
        12 real matches > structural cap of 8 -> must be rejected with a
        clear French message.
        """
        t = TournamentFactory(owner=user)
        PairFactory.create_batch(64, tournament=t)
        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 64,
                "nb_pair_round_64": 32,
                "nb_pair_round_32": 16,
                "nb_pair_round_16": 8,
                "nb_pair_round_8": 4,
                "nb_pair_round_4": 4,
            },
            format="json",
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "fields" not in data or not data.get("fields")
        assert "16" in data["message"]
        assert "8" in data["message"]
        assert "message" in data
