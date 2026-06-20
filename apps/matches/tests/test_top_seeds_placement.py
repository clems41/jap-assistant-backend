import pytest

from apps.matches.models import Bracket, Match, Round
from apps.players.tests.factories import PairFactory
from apps.tournaments.tests.factories import TournamentFactory


def _bracket_url(tournament_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/bracket/"


def _zero_seeding() -> dict:
    return {
        "nb_pair_round_64": 0,
        "nb_pair_round_32": 0,
        "nb_pair_round_16": 0,
        "nb_pair_round_8": 0,
        "nb_pair_round_4": 0,
    }


@pytest.mark.django_db
class TestTopSeedsPlacement:
    def test_ticket_example_1_dimension_16_12_pairs(
        self, authenticated_client, user
    ):
        """dimension=16, 12 pairs, nb_pair_round_16=8, nb_pair_round_8=4 (rest 0)
        -> entry round is QUART_DE_FINALE (round_size=8, 4 matches):
        TS1 -> pair2 of quart #4, TS2 -> pair1 of quart #1.
        """
        t = TournamentFactory(owner=user)
        ts1 = PairFactory(tournament=t, weight=1.0)
        ts2 = PairFactory(tournament=t, weight=2.0)
        PairFactory.create_batch(10, tournament=t, weight=100.0)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
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
        assert resp.status_code == 201

        bracket = Bracket.objects.get(tournament=t, parent__isnull=True)
        quart4 = Match.objects.get(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=4
        )
        quart1 = Match.objects.get(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=1
        )
        assert quart4.pair2_id == ts1.pk
        assert quart1.pair1_id == ts2.pk

    def test_ticket_example_2_dimension_16_16_pairs(
        self, authenticated_client, user
    ):
        """dimension=16, 16 pairs, nb_pair_round_16=16 (rest 0)
        -> entry round is HUITIEME_DE_FINALE (round_size=16, 8 matches):
        TS1 -> pair2 of huitieme #8, TS2 -> pair1 of huitieme #1.
        """
        t = TournamentFactory(owner=user)
        ts1 = PairFactory(tournament=t, weight=1.0)
        ts2 = PairFactory(tournament=t, weight=2.0)
        PairFactory.create_batch(14, tournament=t, weight=100.0)

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

        bracket = Bracket.objects.get(tournament=t, parent__isnull=True)
        huitieme8 = Match.objects.get(
            bracket=bracket, round=Round.HUITIEME_DE_FINALE, match_number=8
        )
        huitieme1 = Match.objects.get(
            bracket=bracket, round=Round.HUITIEME_DE_FINALE, match_number=1
        )
        assert huitieme8.pair2_id == ts1.pk
        assert huitieme1.pair1_id == ts2.pk

    def test_seeds_picked_by_ascending_weight_not_creation_order(
        self, authenticated_client, user
    ):
        """Construct pairs out of weight order to prove TS1/TS2 are picked by
        ascending weight, not by creation order or pk."""
        t = TournamentFactory(owner=user)
        PairFactory(tournament=t, weight=100.0)
        PairFactory(tournament=t, weight=50.0)
        ts2 = PairFactory(tournament=t, weight=2.0)
        PairFactory(tournament=t, weight=200.0)
        ts1 = PairFactory(tournament=t, weight=1.0)
        PairFactory.create_batch(7, tournament=t, weight=300.0)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
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
        assert resp.status_code == 201

        bracket = Bracket.objects.get(tournament=t, parent__isnull=True)
        quart4 = Match.objects.get(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=4
        )
        quart1 = Match.objects.get(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=1
        )
        assert quart4.pair2_id == ts1.pk
        assert quart1.pair1_id == ts2.pk

    def test_minimal_case_two_matches_in_entry_round_no_collision(
        self, authenticated_client, user
    ):
        """dimension=8, only nb_pair_round_4=4 nonzero (rest 0), 4 pairs
        -> entry round is DEMIE_FINALE (round_size=4, 2 matches):
        TS1 and TS2 land in two distinct DEMIE_FINALE matches
        (match_number 2 and 1 respectively), no collision.
        """
        t = TournamentFactory(owner=user)
        ts1 = PairFactory(tournament=t, weight=1.0)
        ts2 = PairFactory(tournament=t, weight=2.0)
        PairFactory.create_batch(2, tournament=t, weight=100.0)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 8,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 0,
                "nb_pair_round_16": 0,
                "nb_pair_round_8": 0,
                "nb_pair_round_4": 4,
            },
            format="json",
        )
        assert resp.status_code == 201

        bracket = Bracket.objects.get(tournament=t, parent__isnull=True)
        demie2 = Match.objects.get(
            bracket=bracket, round=Round.DEMIE_FINALE, match_number=2
        )
        demie1 = Match.objects.get(
            bracket=bracket, round=Round.DEMIE_FINALE, match_number=1
        )
        assert demie2.pair2_id == ts1.pk
        assert demie1.pair1_id == ts2.pk

    def test_recompute_placement_flags_disables_bypassed_feeder_match(
        self, authenticated_client, user
    ):
        """In example 1's setup, the HUITIEME_DE_FINALE match that fed the
        now-seeded quart's bypassed slot is disabled=True, while the sibling
        HUITIEME_DE_FINALE match feeding the OTHER slot of that same quart
        match stays disabled=False.
        """
        t = TournamentFactory(owner=user)
        PairFactory(tournament=t, weight=1.0)
        PairFactory(tournament=t, weight=2.0)
        PairFactory.create_batch(10, tournament=t, weight=100.0)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
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
        assert resp.status_code == 201

        bracket = Bracket.objects.get(tournament=t, parent__isnull=True)
        quart4 = Match.objects.get(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=4
        )
        # quart4.pair2 was bypass-seeded with TS1: the huitieme feeding that
        # slot (child2) must be disabled; the sibling huitieme feeding
        # pair1 (child1) must remain enabled.
        bypassed_feeder = Match.objects.get(pk=quart4.child2_id)
        sibling_feeder = Match.objects.get(pk=quart4.child1_id)

        assert bypassed_feeder.disabled is True
        assert sibling_feeder.disabled is False

    def test_no_pairs_no_placement_regression(self, authenticated_client, tournament):
        """A bracket created with 0 pairs and all nb_pair_round_*=0 results in
        no placement at all - root_match pair1/pair2 stay None, matching
        current behavior of existing tests in test_api.py.
        """
        resp = authenticated_client.post(
            _bracket_url(tournament.pk),
            {"dimension": 8, **_zero_seeding()},
            format="json",
        )
        assert resp.status_code == 201
        root = resp.json()["root_match"]
        assert root["pair1"] is None
        assert root["pair2"] is None
