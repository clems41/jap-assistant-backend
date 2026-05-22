"""
Tests for Tournament.status field and recompute_status() logic.

Status transitions:
  DRAFT  → SET    : all pairs weighted + configuration + game_format + >= 2 pairs
  SET    → READY  : all tournament pairs present in BracketSlot
  READY  → SET    : a BracketSlot or BracketState is deleted, or a pair weight becomes null
  SET    → DRAFT  : a pair is deleted below the minimum (< 2 pairs), or a weight becomes null
"""

import pytest

from apps.brackets.tests.factories import BracketSlotFactory, BracketStateFactory
from apps.players.tests.factories import PairFactory
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tournament_with_config(**kwargs) -> Tournament:
    """Return a tournament with game_format and configuration set."""
    return TournamentFactory(
        game_format=Tournament.GameFormat.B1,
        configuration=Tournament.Configuration.TMC,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# TestTournamentStatusDefault
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTournamentStatusDefault:
    def test_tournament_created_with_draft_status(self) -> None:
        tournament = TournamentFactory()
        assert tournament.status == Tournament.Status.DRAFT


# ---------------------------------------------------------------------------
# TestTournamentStatusSetTransition
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTournamentStatusSetTransition:
    def test_status_becomes_set_when_all_conditions_met(self) -> None:
        tournament = _tournament_with_config()
        PairFactory(tournament=tournament, weight=100.0)
        PairFactory(tournament=tournament, weight=200.0)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

    def test_status_remains_draft_with_only_one_pair(self) -> None:
        tournament = _tournament_with_config()
        PairFactory(tournament=tournament, weight=100.0)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_remains_draft_when_pairs_have_no_weight(self) -> None:
        tournament = _tournament_with_config()
        PairFactory(tournament=tournament, weight=None)
        PairFactory(tournament=tournament, weight=None)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_remains_draft_when_configuration_missing(self) -> None:
        tournament = TournamentFactory(
            game_format=Tournament.GameFormat.B1,
            configuration=None,
        )
        PairFactory(tournament=tournament, weight=100.0)
        PairFactory(tournament=tournament, weight=200.0)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_remains_draft_when_game_format_missing(self) -> None:
        tournament = TournamentFactory(
            game_format="",
            configuration=Tournament.Configuration.TMC,
        )
        PairFactory(tournament=tournament, weight=100.0)
        PairFactory(tournament=tournament, weight=200.0)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_reverts_to_draft_when_pair_deleted_below_minimum(self) -> None:
        tournament = _tournament_with_config()
        pair1 = PairFactory(tournament=tournament, weight=100.0)
        PairFactory(tournament=tournament, weight=200.0)

        # Confirm SET first
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

        pair1.delete()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT


# ---------------------------------------------------------------------------
# TestTournamentStatusReadyTransition
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTournamentStatusReadyTransition:
    def test_status_becomes_ready_when_all_pairs_in_bracket(self) -> None:
        tournament = _tournament_with_config()
        pair1 = PairFactory(tournament=tournament, weight=100.0)
        pair2 = PairFactory(tournament=tournament, weight=200.0)

        bracket_state = BracketStateFactory(tournament=tournament)
        BracketSlotFactory(bracket_state=bracket_state, pair=pair1)
        BracketSlotFactory(bracket_state=bracket_state, pair=pair2)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.READY

    def test_status_stays_set_when_not_all_pairs_in_bracket(self) -> None:
        tournament = _tournament_with_config()
        pair1 = PairFactory(tournament=tournament, weight=100.0)
        PairFactory(tournament=tournament, weight=200.0)

        bracket_state = BracketStateFactory(tournament=tournament)
        # Only pair1 is in the bracket — pair2 is missing
        BracketSlotFactory(bracket_state=bracket_state, pair=pair1)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

    def test_status_reverts_to_set_when_bracket_slot_deleted(self) -> None:
        tournament = _tournament_with_config()
        pair1 = PairFactory(tournament=tournament, weight=100.0)
        pair2 = PairFactory(tournament=tournament, weight=200.0)

        bracket_state = BracketStateFactory(tournament=tournament)
        slot1 = BracketSlotFactory(bracket_state=bracket_state, pair=pair1)
        BracketSlotFactory(bracket_state=bracket_state, pair=pair2)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.READY

        slot1.delete()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

    def test_status_reverts_to_set_when_bracket_state_deleted(self) -> None:
        tournament = _tournament_with_config()
        pair1 = PairFactory(tournament=tournament, weight=100.0)
        pair2 = PairFactory(tournament=tournament, weight=200.0)

        bracket_state = BracketStateFactory(tournament=tournament)
        BracketSlotFactory(bracket_state=bracket_state, pair=pair1)
        BracketSlotFactory(bracket_state=bracket_state, pair=pair2)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.READY

        bracket_state.delete()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

    def test_status_reverts_to_draft_when_pair_weight_becomes_null(self) -> None:
        """When a pair weight becomes null, the SET conditions are no longer
        met, so the status falls back to DRAFT (not SET), even from READY."""
        tournament = _tournament_with_config()
        pair1 = PairFactory(tournament=tournament, weight=100.0)
        pair2 = PairFactory(tournament=tournament, weight=200.0)

        bracket_state = BracketStateFactory(tournament=tournament)
        BracketSlotFactory(bracket_state=bracket_state, pair=pair1)
        BracketSlotFactory(bracket_state=bracket_state, pair=pair2)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.READY

        # Nullify the ranking of player1 → pair1 weight becomes null
        player1 = pair1.player1
        player1.ranking = None
        player1.save()
        # Simulate weight being nullified when player ranking is lost
        pair1.weight = None
        pair1.save()

        # SET requires all pairs to have a non-null weight, so the result
        # is DRAFT rather than SET.
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT
