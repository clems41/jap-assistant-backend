"""
Tests for Tournament.status field and recompute_status() logic.

Status transitions:
  DRAFT  → SET    : all pairs weighted + all players ranked + configuration + game_format + >= 4 pairs
  SET    → DRAFT  : a pair is deleted below the minimum (< 4 pairs), a weight becomes null,
                    or a player's ranking becomes null

Note: SET → READY transition is not yet implemented (brackets app removed).
READY remains in Tournament.Status.choices for future use.
"""

import pytest

from apps.players.tests.factories import PairFactory, PlayerFactory
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
        for i in range(4):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

    def test_status_remains_draft_with_fewer_than_four_pairs(self) -> None:
        tournament = _tournament_with_config()
        for i in range(3):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_remains_draft_when_pairs_have_no_weight(self) -> None:
        tournament = _tournament_with_config()
        for _ in range(4):
            PairFactory(tournament=tournament, weight=None)

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_remains_draft_when_player_has_no_ranking(self) -> None:
        tournament = _tournament_with_config()
        player_without_ranking = PlayerFactory(ranking=None)
        PairFactory(tournament=tournament, weight=100.0, player1=player_without_ranking)
        for i in range(3):
            PairFactory(tournament=tournament, weight=float(200 + i * 10))

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_remains_draft_when_configuration_missing(self) -> None:
        tournament = TournamentFactory(
            game_format=Tournament.GameFormat.B1,
            configuration=None,
        )
        for i in range(4):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_remains_draft_when_game_format_missing(self) -> None:
        tournament = TournamentFactory(
            game_format="",
            configuration=Tournament.Configuration.TMC,
        )
        for i in range(4):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_becomes_set_when_game_format_and_configuration_updated(self) -> None:
        tournament = TournamentFactory(game_format="", configuration=None)
        for i in range(4):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        tournament.game_format = Tournament.GameFormat.B1
        tournament.configuration = Tournament.Configuration.TMC
        tournament.save()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

    def test_status_reverts_to_draft_when_pair_deleted_below_minimum(self) -> None:
        tournament = _tournament_with_config()
        pairs = [PairFactory(tournament=tournament, weight=float(100 + i * 10)) for i in range(4)]

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

        pairs[0].delete()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_reverts_to_draft_when_player_ranking_removed(self) -> None:
        tournament = _tournament_with_config()
        pairs = [PairFactory(tournament=tournament, weight=float(100 + i * 10)) for i in range(4)]

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

        player = pairs[0].player1
        player.ranking = None
        player.save()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT
