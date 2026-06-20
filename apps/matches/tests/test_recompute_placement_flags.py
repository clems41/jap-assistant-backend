import pytest

from apps.matches.models import Round
from apps.matches.tests.factories import BracketFactory, MatchFactory
from apps.players.tests.factories import PairFactory


@pytest.mark.django_db
class TestRecomputePlacementFlagsDimension8:
    """Direct unit tests of Bracket.recompute_placement_flags(), built purely
    with factories (no HTTP), to pin down the algorithm independently of the
    API layer.

    Tree shape (dimension 8):
        finale
          child1 = demie1, child2 = demie2
        demie1
          child1 = quart1, child2 = quart2
        demie2
          child1 = quart3, child2 = quart4
    """

    @pytest.fixture
    def tree(self, tournament):
        bracket = BracketFactory(tournament=tournament)
        quart1 = MatchFactory(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=1
        )
        quart2 = MatchFactory(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=2
        )
        quart3 = MatchFactory(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=3
        )
        quart4 = MatchFactory(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=4
        )
        demie1 = MatchFactory(
            bracket=bracket,
            round=Round.DEMIE_FINALE,
            match_number=1,
            child1=quart1,
            child2=quart2,
        )
        demie2 = MatchFactory(
            bracket=bracket,
            round=Round.DEMIE_FINALE,
            match_number=2,
            child1=quart3,
            child2=quart4,
        )
        finale = MatchFactory(
            bracket=bracket,
            round=Round.FINALE,
            match_number=1,
            child1=demie1,
            child2=demie2,
        )
        return {
            "bracket": bracket,
            "quart1": quart1,
            "quart2": quart2,
            "quart3": quart3,
            "quart4": quart4,
            "demie1": demie1,
            "demie2": demie2,
            "finale": finale,
        }

    def test_no_placements_everything_enabled(self, tree):
        tree["bracket"].recompute_placement_flags()
        for key in (
            "quart1",
            "quart2",
            "quart3",
            "quart4",
            "demie1",
            "demie2",
            "finale",
        ):
            m = tree[key]
            m.refresh_from_db()
            assert m.disabled is False
            assert m.pair1_can_be_placed is True
            assert m.pair2_can_be_placed is True

    def test_bypass_placement_on_demie1_pair1_disables_quart1_only(
        self, tree, tournament
    ):
        pair = PairFactory(tournament=tournament)
        demie1 = tree["demie1"]
        demie1.pair1 = pair
        demie1.save(update_fields=["pair1"])

        tree["bracket"].recompute_placement_flags()

        tree["quart1"].refresh_from_db()
        tree["quart2"].refresh_from_db()
        assert tree["quart1"].disabled is True
        assert tree["quart1"].pair1_can_be_placed is False
        assert tree["quart1"].pair2_can_be_placed is False
        assert tree["quart2"].disabled is False
        assert tree["quart2"].pair1_can_be_placed is True
        assert tree["quart2"].pair2_can_be_placed is True

    def test_bypass_placement_on_demie1_pair2_disables_quart2_only(
        self, tree, tournament
    ):
        pair = PairFactory(tournament=tournament)
        demie1 = tree["demie1"]
        demie1.pair2 = pair
        demie1.save(update_fields=["pair2"])

        tree["bracket"].recompute_placement_flags()

        tree["quart1"].refresh_from_db()
        tree["quart2"].refresh_from_db()
        assert tree["quart2"].disabled is True
        assert tree["quart2"].pair1_can_be_placed is False
        assert tree["quart2"].pair2_can_be_placed is False
        assert tree["quart1"].disabled is False
        assert tree["quart1"].pair1_can_be_placed is True
        assert tree["quart1"].pair2_can_be_placed is True

    def test_placement_on_quart1_blocks_demie1_pair1_and_finale_pair1(
        self, tree, tournament
    ):
        pair = PairFactory(tournament=tournament)
        quart1 = tree["quart1"]
        quart1.pair1 = pair
        quart1.save(update_fields=["pair1"])

        tree["bracket"].recompute_placement_flags()

        tree["demie1"].refresh_from_db()
        tree["finale"].refresh_from_db()
        assert tree["demie1"].pair1_can_be_placed is False
        assert tree["demie1"].pair2_can_be_placed is True
        assert tree["finale"].pair1_can_be_placed is False
        assert tree["finale"].pair2_can_be_placed is True

    def test_placement_on_quart2_blocks_demie1_pair2_and_finale_pair1(
        self, tree, tournament
    ):
        pair = PairFactory(tournament=tournament)
        quart2 = tree["quart2"]
        quart2.pair1 = pair
        quart2.save(update_fields=["pair1"])

        tree["bracket"].recompute_placement_flags()

        tree["demie1"].refresh_from_db()
        tree["finale"].refresh_from_db()
        assert tree["demie1"].pair2_can_be_placed is False
        assert tree["demie1"].pair1_can_be_placed is True
        assert tree["finale"].pair1_can_be_placed is False
        assert tree["finale"].pair2_can_be_placed is True

    def test_placement_on_quart3_blocks_demie2_pair1_and_finale_pair2(
        self, tree, tournament
    ):
        pair = PairFactory(tournament=tournament)
        quart3 = tree["quart3"]
        quart3.pair1 = pair
        quart3.save(update_fields=["pair1"])

        tree["bracket"].recompute_placement_flags()

        tree["demie2"].refresh_from_db()
        tree["finale"].refresh_from_db()
        assert tree["demie2"].pair1_can_be_placed is False
        assert tree["demie2"].pair2_can_be_placed is True
        assert tree["finale"].pair2_can_be_placed is False
        assert tree["finale"].pair1_can_be_placed is True

    def test_reversal_restores_quart1_state(self, tree, tournament):
        pair = PairFactory(tournament=tournament)
        demie1 = tree["demie1"]
        demie1.pair1 = pair
        demie1.save(update_fields=["pair1"])
        tree["bracket"].recompute_placement_flags()

        tree["quart1"].refresh_from_db()
        assert tree["quart1"].disabled is True

        demie1.pair1 = None
        demie1.save(update_fields=["pair1"])
        tree["bracket"].recompute_placement_flags()

        tree["quart1"].refresh_from_db()
        assert tree["quart1"].disabled is False
        assert tree["quart1"].pair1_can_be_placed is True
        assert tree["quart1"].pair2_can_be_placed is True

    def test_reversal_still_blocked_by_sibling_placement(self, tree, tournament):
        pair_a = PairFactory(tournament=tournament)
        pair_b = PairFactory(tournament=tournament)
        quart1 = tree["quart1"]
        quart2 = tree["quart2"]
        quart1.pair1 = pair_a
        quart1.save(update_fields=["pair1"])
        quart2.pair1 = pair_b
        quart2.save(update_fields=["pair1"])

        tree["bracket"].recompute_placement_flags()
        tree["finale"].refresh_from_db()
        assert tree["finale"].pair1_can_be_placed is False

        quart1.pair1 = None
        quart1.save(update_fields=["pair1"])
        tree["bracket"].recompute_placement_flags()

        tree["finale"].refresh_from_db()
        assert tree["finale"].pair1_can_be_placed is False

    def test_winner_propagation_does_not_disable_child(self, tree, tournament):
        """A parent slot filled with the child's actual winner (legitimate
        propagation) must NOT disable the child match."""
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        quart1 = tree["quart1"]
        quart1.pair1 = pair1
        quart1.pair2 = pair2
        quart1.winner = pair1
        quart1.save(update_fields=["pair1", "pair2", "winner"])

        demie1 = tree["demie1"]
        demie1.pair1 = pair1
        demie1.save(update_fields=["pair1"])

        tree["bracket"].recompute_placement_flags()

        quart1.refresh_from_db()
        assert quart1.disabled is False


@pytest.mark.django_db
class TestRecomputePlacementFlagsDimension16:
    """Two-level downward cascade: bypass-placing directly on the finale's
    pair1 must disable demie1 AND both of its quart children AND all 4
    huitieme grandchildren under that branch, while leaving demie2's entire
    branch untouched."""

    @pytest.fixture
    def tree(self, tournament):
        bracket = BracketFactory(tournament=tournament, dimension=16)

        huit = [
            MatchFactory(
                bracket=bracket, round=Round.HUITIEME_DE_FINALE, match_number=i + 1
            )
            for i in range(8)
        ]
        quart = [
            MatchFactory(
                bracket=bracket,
                round=Round.QUART_DE_FINALE,
                match_number=i + 1,
                child1=huit[2 * i],
                child2=huit[2 * i + 1],
            )
            for i in range(4)
        ]
        demie1 = MatchFactory(
            bracket=bracket,
            round=Round.DEMIE_FINALE,
            match_number=1,
            child1=quart[0],
            child2=quart[1],
        )
        demie2 = MatchFactory(
            bracket=bracket,
            round=Round.DEMIE_FINALE,
            match_number=2,
            child1=quart[2],
            child2=quart[3],
        )
        finale = MatchFactory(
            bracket=bracket,
            round=Round.FINALE,
            match_number=1,
            child1=demie1,
            child2=demie2,
        )
        return {
            "bracket": bracket,
            "huit": huit,
            "quart": quart,
            "demie1": demie1,
            "demie2": demie2,
            "finale": finale,
        }

    def test_bypass_on_finale_disables_entire_demie1_branch(self, tree, tournament):
        pair = PairFactory(tournament=tournament)
        finale = tree["finale"]
        finale.pair1 = pair
        finale.save(update_fields=["pair1"])

        tree["bracket"].recompute_placement_flags()

        tree["demie1"].refresh_from_db()
        assert tree["demie1"].disabled is True
        assert tree["demie1"].pair1_can_be_placed is False
        assert tree["demie1"].pair2_can_be_placed is False

        for m in (tree["quart"][0], tree["quart"][1]):
            m.refresh_from_db()
            assert m.disabled is True
            assert m.pair1_can_be_placed is False
            assert m.pair2_can_be_placed is False

        for m in (tree["huit"][0], tree["huit"][1], tree["huit"][2], tree["huit"][3]):
            m.refresh_from_db()
            assert m.disabled is True
            assert m.pair1_can_be_placed is False
            assert m.pair2_can_be_placed is False

    def test_bypass_on_finale_leaves_demie2_branch_untouched(self, tree, tournament):
        pair = PairFactory(tournament=tournament)
        finale = tree["finale"]
        finale.pair1 = pair
        finale.save(update_fields=["pair1"])

        tree["bracket"].recompute_placement_flags()

        tree["demie2"].refresh_from_db()
        assert tree["demie2"].disabled is False
        assert tree["demie2"].pair1_can_be_placed is True
        assert tree["demie2"].pair2_can_be_placed is True

        for m in (tree["quart"][2], tree["quart"][3]):
            m.refresh_from_db()
            assert m.disabled is False
            assert m.pair1_can_be_placed is True
            assert m.pair2_can_be_placed is True

        for m in (tree["huit"][4], tree["huit"][5], tree["huit"][6], tree["huit"][7]):
            m.refresh_from_db()
            assert m.disabled is False
            assert m.pair1_can_be_placed is True
            assert m.pair2_can_be_placed is True


@pytest.mark.django_db
class TestRecomputePlacementFlagsStructuralConstraint:
    """Structural constraint driven purely by nb_pair_round_X, independent
    of any actual pair placement, for every round other than the "premier
    tour" (the largest round size with a nonzero nb_pair_round_X):

    - when a round's nonzero nb_pair_round_X exactly matches its number of
      active matches, each of those matches is forced to accept a
      placement on only one side, and the entire subtree feeding the
      other side is force-disabled.
    - when a round's nb_pair_round_X is 0, no pair is ever meant to enter
      it directly, so both placement slots are locked on every active
      match in it (the match itself stays active, to be decided by its
      sub-match winners)."""

    @pytest.fixture
    def tree_dim8(self, tournament):
        bracket = BracketFactory(tournament=tournament)
        quart1 = MatchFactory(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=1
        )
        quart2 = MatchFactory(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=2
        )
        quart3 = MatchFactory(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=3
        )
        quart4 = MatchFactory(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=4
        )
        demie1 = MatchFactory(
            bracket=bracket,
            round=Round.DEMIE_FINALE,
            match_number=1,
            child1=quart1,
            child2=quart2,
        )
        demie2 = MatchFactory(
            bracket=bracket,
            round=Round.DEMIE_FINALE,
            match_number=2,
            child1=quart3,
            child2=quart4,
        )
        finale = MatchFactory(
            bracket=bracket,
            round=Round.FINALE,
            match_number=1,
            child1=demie1,
            child2=demie2,
        )
        return {
            "bracket": bracket,
            "quart1": quart1,
            "quart2": quart2,
            "quart3": quart3,
            "quart4": quart4,
            "demie1": demie1,
            "demie2": demie2,
            "finale": finale,
        }

    def test_minimal_two_round_constraint_forces_pair1_and_pair2_only(self, tree_dim8):
        bracket = tree_dim8["bracket"]
        bracket.nb_pair_round_8 = 2
        bracket.nb_pair_round_4 = 2
        bracket.save(update_fields=["nb_pair_round_8", "nb_pair_round_4"])

        bracket.recompute_placement_flags()

        tree_dim8["demie1"].refresh_from_db()
        tree_dim8["demie2"].refresh_from_db()
        tree_dim8["quart1"].refresh_from_db()
        tree_dim8["quart2"].refresh_from_db()
        tree_dim8["quart3"].refresh_from_db()
        tree_dim8["quart4"].refresh_from_db()

        assert tree_dim8["demie1"].pair1_can_be_placed is True
        assert tree_dim8["demie1"].pair2_can_be_placed is False
        assert tree_dim8["demie2"].pair1_can_be_placed is False
        assert tree_dim8["demie2"].pair2_can_be_placed is True

        assert tree_dim8["quart1"].disabled is True
        assert tree_dim8["quart4"].disabled is True

        assert tree_dim8["quart2"].disabled is False
        assert tree_dim8["quart2"].pair1_can_be_placed is True
        assert tree_dim8["quart2"].pair2_can_be_placed is True

        assert tree_dim8["quart3"].disabled is False
        assert tree_dim8["quart3"].pair1_can_be_placed is True
        assert tree_dim8["quart3"].pair2_can_be_placed is True

    def test_unconstrained_passthrough_when_nb_pair_round_x_not_equal_active_count(
        self, tree_dim8
    ):
        bracket = tree_dim8["bracket"]
        bracket.nb_pair_round_8 = 4
        bracket.nb_pair_round_4 = 1
        bracket.save(update_fields=["nb_pair_round_8", "nb_pair_round_4"])

        bracket.recompute_placement_flags()

        tree_dim8["demie1"].refresh_from_db()
        tree_dim8["demie2"].refresh_from_db()

        assert tree_dim8["demie1"].pair1_can_be_placed is True
        assert tree_dim8["demie1"].pair2_can_be_placed is True
        assert tree_dim8["demie2"].pair1_can_be_placed is True
        assert tree_dim8["demie2"].pair2_can_be_placed is True

        for key in ("quart1", "quart2", "quart3", "quart4"):
            tree_dim8[key].refresh_from_db()
            assert tree_dim8[key].disabled is False

    def test_single_entrant_round_locks_other_rounds_with_zero_entrants(
        self, tree_dim8
    ):
        bracket = tree_dim8["bracket"]
        bracket.nb_pair_round_8 = 4
        bracket.save(update_fields=["nb_pair_round_8"])

        bracket.recompute_placement_flags()

        for key in ("quart1", "quart2", "quart3", "quart4"):
            tree_dim8[key].refresh_from_db()
            assert tree_dim8[key].disabled is False

        # QUART_DE_FINALE is the premier tour (nb_pair_round_8=4, largest
        # nonzero entrant size) and stays free. DEMIE_FINALE is NOT the
        # premier tour and has nb_pair_round_4=0 (default): no pair is ever
        # meant to enter it directly, so both slots must be locked on every
        # active demie match.
        tree_dim8["demie1"].refresh_from_db()
        tree_dim8["demie2"].refresh_from_db()
        assert tree_dim8["demie1"].pair1_can_be_placed is False
        assert tree_dim8["demie1"].pair2_can_be_placed is False
        assert tree_dim8["demie2"].pair1_can_be_placed is False
        assert tree_dim8["demie2"].pair2_can_be_placed is False

    @pytest.fixture
    def tree_dim16(self, tournament):
        bracket = BracketFactory(tournament=tournament, dimension=16)

        huit = [
            MatchFactory(
                bracket=bracket, round=Round.HUITIEME_DE_FINALE, match_number=i + 1
            )
            for i in range(8)
        ]
        quart = [
            MatchFactory(
                bracket=bracket,
                round=Round.QUART_DE_FINALE,
                match_number=i + 1,
                child1=huit[2 * i],
                child2=huit[2 * i + 1],
            )
            for i in range(4)
        ]
        demie1 = MatchFactory(
            bracket=bracket,
            round=Round.DEMIE_FINALE,
            match_number=1,
            child1=quart[0],
            child2=quart[1],
        )
        demie2 = MatchFactory(
            bracket=bracket,
            round=Round.DEMIE_FINALE,
            match_number=2,
            child1=quart[2],
            child2=quart[3],
        )
        finale = MatchFactory(
            bracket=bracket,
            round=Round.FINALE,
            match_number=1,
            child1=demie1,
            child2=demie2,
        )
        return {
            "bracket": bracket,
            "huit": huit,
            "quart": quart,
            "demie1": demie1,
            "demie2": demie2,
            "finale": finale,
        }

    def test_gap_round_with_zero_entrants_is_locked(self, tree_dim16):
        bracket = tree_dim16["bracket"]
        bracket.nb_pair_round_16 = 8
        bracket.nb_pair_round_8 = 0
        bracket.nb_pair_round_4 = 2
        bracket.save(
            update_fields=["nb_pair_round_16", "nb_pair_round_8", "nb_pair_round_4"]
        )

        bracket.recompute_placement_flags()

        tree_dim16["demie1"].refresh_from_db()
        tree_dim16["demie2"].refresh_from_db()
        assert tree_dim16["demie1"].pair1_can_be_placed is True
        assert tree_dim16["demie1"].pair2_can_be_placed is False
        assert tree_dim16["demie2"].pair1_can_be_placed is False
        assert tree_dim16["demie2"].pair2_can_be_placed is True

        tree_dim16["quart"][0].refresh_from_db()
        tree_dim16["huit"][0].refresh_from_db()
        tree_dim16["huit"][1].refresh_from_db()
        assert tree_dim16["quart"][0].disabled is True
        assert tree_dim16["huit"][0].disabled is True
        assert tree_dim16["huit"][1].disabled is True

        tree_dim16["quart"][3].refresh_from_db()
        tree_dim16["huit"][6].refresh_from_db()
        tree_dim16["huit"][7].refresh_from_db()
        assert tree_dim16["quart"][3].disabled is True
        assert tree_dim16["huit"][6].disabled is True
        assert tree_dim16["huit"][7].disabled is True

        # quart[1] and quart[2] sit in the gap round (nb_pair_round_8=0):
        # no entrant is ever meant to be placed directly into QUART_DE_FINALE
        # here, but the matches are still real and must be played out from
        # their huitieme winners below, so they stay active (disabled=False)
        # while both placement slots are locked.
        tree_dim16["quart"][1].refresh_from_db()
        assert tree_dim16["quart"][1].disabled is False
        assert tree_dim16["quart"][1].pair1_can_be_placed is False
        assert tree_dim16["quart"][1].pair2_can_be_placed is False

        tree_dim16["quart"][2].refresh_from_db()
        assert tree_dim16["quart"][2].disabled is False
        assert tree_dim16["quart"][2].pair1_can_be_placed is False
        assert tree_dim16["quart"][2].pair2_can_be_placed is False
