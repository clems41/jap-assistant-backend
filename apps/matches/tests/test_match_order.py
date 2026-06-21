import pytest

from apps.matches.models import Bracket, Match
from apps.matches.services import (
    assign_match_order,
    generate_classification_brackets,
    generate_match_tree,
)
from apps.matches.tests.factories import MatchFactory
from apps.players.tests.factories import PairFactory
from apps.tournaments.tests.factories import TournamentFactory


@pytest.mark.django_db
class TestMatchOrderField:
    def test_default_order_is_zero(self):
        match = MatchFactory()
        assert match.order == 0


@pytest.mark.django_db
class TestAssignMatchOrderSimpleCase:
    """dim=4, nb_pair_round_4=4 (full entry, no top seeds): 2 DEMIE_FINALE
    matches -> order 1-2; classification bracket dim=2 (source_round=
    DEMIE_FINALE, places 3-4) -> order 3; main FINALE -> order 4 (last).
    """

    def test_dimension_4_full_entry(self):
        tournament = TournamentFactory()
        PairFactory.create_batch(4, tournament=tournament)
        tournament.refresh_from_db()
        main_bracket = Bracket.objects.create(
            tournament=tournament,
            dimension=4,
            nb_pair_round_4=4,
        )
        generate_match_tree(main_bracket, tournament.game_format)
        generate_classification_brackets(main_bracket, tournament)

        assign_match_order(main_bracket)

        demies = list(
            Match.objects.filter(bracket=main_bracket, round="DEMIE_FINALE").order_by(
                "match_number"
            )
        )
        assert [m.order for m in demies] == [1, 2]

        classification_bracket = Bracket.objects.get(
            parent=main_bracket, source_round="DEMIE_FINALE"
        )
        classification_match = Match.objects.get(bracket=classification_bracket)
        assert classification_match.order == 3

        finale = Match.objects.get(bracket=main_bracket, round="FINALE")
        assert finale.order == 4


@pytest.mark.django_db
class TestAssignMatchOrderDimension32WorkedExample:
    """dim=32, 16 pairs, seeding nb_pair_round_32=8, nb_pair_round_16=4,
    nb_pair_round_8=4: 4 classification brackets at places 13-16/9-12/5-8/3-4,
    sourced at SEIZIEME/HUITIEME/QUART/DEMIE_FINALE respectively.

    Expected order ranges:
    - 1-16: main SEIZIEME matches
    - 17-20: SEIZIEME-sourced classification subtree (places 13-16, cascades
      to a dim=2 child at places 15-16)
    - 21-28: main HUITIEME matches
    - 29-32: HUITIEME-sourced subtree (places 9-12)
    - 33-36: main QUART matches
    - 37-40: QUART-sourced subtree (places 5-8)
    - 41-42: main DEMIE_FINALE matches
    - 43: DEMIE_FINALE-sourced subtree (single dim=2 match, places 3-4)
    - 44: main FINALE (last of all)
    Total: 44 matches (31 main + 13 classification), orders exactly 1..44.
    """

    @pytest.fixture
    def main_bracket(self):
        tournament = TournamentFactory()
        PairFactory.create_batch(16, tournament=tournament)
        tournament.refresh_from_db()
        bracket = Bracket.objects.create(
            tournament=tournament,
            dimension=32,
            nb_pair_round_32=8,
            nb_pair_round_16=4,
            nb_pair_round_8=4,
        )
        generate_match_tree(bracket, tournament.game_format)
        generate_classification_brackets(bracket, tournament)
        assign_match_order(bracket)
        return bracket

    def test_main_seizieme_order_range(self, main_bracket):
        matches = Match.objects.filter(
            bracket=main_bracket, round="SEIZIEME_DE_FINALE"
        ).order_by("match_number")
        assert [m.order for m in matches] == list(range(1, 17))

    def test_seizieme_sourced_subtree_order_range(self, main_bracket):
        classification_bracket = Bracket.objects.get(
            parent=main_bracket, source_round="SEIZIEME_DE_FINALE"
        )
        subtree_orders = self._subtree_orders(classification_bracket)
        assert sorted(subtree_orders) == list(range(17, 21))

    def test_main_huitieme_order_range(self, main_bracket):
        matches = Match.objects.filter(
            bracket=main_bracket, round="HUITIEME_DE_FINALE"
        ).order_by("match_number")
        assert [m.order for m in matches] == list(range(21, 29))

    def test_huitieme_sourced_subtree_order_range(self, main_bracket):
        classification_bracket = Bracket.objects.get(
            parent=main_bracket, source_round="HUITIEME_DE_FINALE"
        )
        subtree_orders = self._subtree_orders(classification_bracket)
        assert sorted(subtree_orders) == list(range(29, 33))

    def test_main_quart_order_range(self, main_bracket):
        matches = Match.objects.filter(
            bracket=main_bracket, round="QUART_DE_FINALE"
        ).order_by("match_number")
        assert [m.order for m in matches] == list(range(33, 37))

    def test_quart_sourced_subtree_order_range(self, main_bracket):
        classification_bracket = Bracket.objects.get(
            parent=main_bracket, source_round="QUART_DE_FINALE"
        )
        subtree_orders = self._subtree_orders(classification_bracket)
        assert sorted(subtree_orders) == list(range(37, 41))

    def test_main_demie_finale_order_range(self, main_bracket):
        matches = Match.objects.filter(
            bracket=main_bracket, round="DEMIE_FINALE"
        ).order_by("match_number")
        assert [m.order for m in matches] == [41, 42]

    def test_demie_finale_sourced_subtree_order(self, main_bracket):
        classification_bracket = Bracket.objects.get(
            parent=main_bracket, source_round="DEMIE_FINALE"
        )
        match = Match.objects.get(bracket=classification_bracket)
        assert match.order == 43

    def test_main_finale_is_last(self, main_bracket):
        finale = Match.objects.get(bracket=main_bracket, round="FINALE")
        assert finale.order == 44

    def test_global_invariant_no_gaps_no_duplicates(self, main_bracket):
        all_orders = list(
            Match.objects.filter(
                bracket__tournament=main_bracket.tournament
            ).values_list("order", flat=True)
        )
        assert len(all_orders) == 44
        assert sorted(all_orders) == list(range(1, 45))

    @staticmethod
    def _subtree_orders(bracket: Bracket) -> list[int]:
        orders = list(
            Match.objects.filter(bracket=bracket).values_list("order", flat=True)
        )
        for child in Bracket.objects.filter(parent=bracket):
            orders.extend(
                TestAssignMatchOrderDimension32WorkedExample._subtree_orders(child)
            )
        return orders


@pytest.mark.django_db
class TestAssignMatchOrderGenerationIntegration:
    def test_post_bracket_assigns_order_to_all_matches(
        self, authenticated_client, tournament
    ):
        """dimension=8 is the smallest dimension accepted by the bracket
        generation endpoint (VALID_DIMENSIONS = {8, 16, 32, 64})."""
        PairFactory.create_batch(8, tournament=tournament)
        resp = authenticated_client.post(
            f"/api/v1/tournaments/{tournament.pk}/bracket/",
            {
                "dimension": 8,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 0,
                "nb_pair_round_16": 0,
                "nb_pair_round_8": 8,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        assert resp.status_code == 201

        orders = list(
            Match.objects.filter(bracket__tournament=tournament).values_list(
                "order", flat=True
            )
        )
        assert sorted(orders) == list(range(1, len(orders) + 1))


@pytest.mark.django_db
class TestMatchOrderSerialization:
    def test_get_bracket_root_match_order_matches_db(
        self, authenticated_client, tournament
    ):
        PairFactory.create_batch(8, tournament=tournament)
        resp = authenticated_client.post(
            f"/api/v1/tournaments/{tournament.pk}/bracket/",
            {
                "dimension": 8,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 0,
                "nb_pair_round_16": 0,
                "nb_pair_round_8": 8,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        assert resp.status_code == 201

        resp = authenticated_client.get(f"/api/v1/tournaments/{tournament.pk}/bracket/")
        assert resp.status_code == 200
        root_match = resp.json()["root_match"]

        finale = Match.objects.get(
            bracket__tournament=tournament,
            bracket__parent__isnull=True,
            round="FINALE",
        )
        assert root_match["order"] == finale.order
