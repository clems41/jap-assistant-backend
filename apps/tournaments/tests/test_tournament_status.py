"""
Tests for Tournament.status field and recompute_status() logic.

Status transitions:
  DRAFT  → SET    : all pairs weighted + configuration + game_format + >= 2 pairs
  SET    → DRAFT  : a pair is deleted below the minimum (< 2 pairs), or a weight becomes null

Note: SET → READY transition is not yet implemented (brackets app removed).
READY remains in Tournament.Status.choices for future use.
"""

import pytest

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


