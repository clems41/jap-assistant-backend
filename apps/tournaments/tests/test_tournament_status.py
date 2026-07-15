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

    def test_status_becomes_set_when_game_format_and_configuration_updated(
        self,
    ) -> None:
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
        pairs = [
            PairFactory(tournament=tournament, weight=float(100 + i * 10))
            for i in range(4)
        ]

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

        pairs[0].delete()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT

    def test_status_reverts_to_draft_when_player_ranking_removed(self) -> None:
        tournament = _tournament_with_config()
        pairs = [
            PairFactory(tournament=tournament, weight=float(100 + i * 10))
            for i in range(4)
        ]

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

        player = pairs[0].player1
        player.ranking = None
        player.save()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT


# ---------------------------------------------------------------------------
# TestTournamentStatusStartedFinishedTransitions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTournamentStatusStartedFinishedTransitions:
    def test_mark_as_started_from_draft(self) -> None:
        tournament = TournamentFactory()
        assert tournament.status == Tournament.Status.DRAFT

        tournament.mark_as_started()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

    def test_mark_as_started_from_set(self) -> None:
        tournament = _tournament_with_config()
        for i in range(4):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

        tournament.mark_as_started()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

    def test_mark_as_started_is_noop_when_already_started(self) -> None:
        tournament = TournamentFactory()

        tournament.mark_as_started()
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

        tournament.mark_as_started()
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

    def test_mark_as_started_is_noop_when_already_finished(self) -> None:
        tournament = TournamentFactory()
        tournament.status = Tournament.Status.FINISHED
        tournament.save()

        tournament.mark_as_started()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

    def test_mark_as_finished_from_started(self) -> None:
        tournament = TournamentFactory()
        tournament.mark_as_started()

        tournament.mark_as_finished()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

    def test_mark_as_finished_is_noop_when_already_finished(self) -> None:
        tournament = TournamentFactory()
        tournament.mark_as_started()
        tournament.mark_as_finished()

        tournament.mark_as_finished()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED


# ---------------------------------------------------------------------------
# TestTournamentIsLockedIsFinished
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTournamentIsLockedIsFinished:
    @pytest.mark.parametrize(
        "tournament_status",
        [Tournament.Status.DRAFT, Tournament.Status.SET, Tournament.Status.READY],
    )
    def test_is_locked_false_for_editable_statuses(self, tournament_status) -> None:
        tournament = TournamentFactory(status=tournament_status)
        assert tournament.is_locked is False

    @pytest.mark.parametrize(
        "tournament_status",
        [Tournament.Status.STARTED, Tournament.Status.FINISHED],
    )
    def test_is_locked_true_for_locked_statuses(self, tournament_status) -> None:
        tournament = TournamentFactory(status=tournament_status)
        assert tournament.is_locked is True

    @pytest.mark.parametrize(
        "tournament_status",
        [
            Tournament.Status.DRAFT,
            Tournament.Status.SET,
            Tournament.Status.READY,
            Tournament.Status.STARTED,
        ],
    )
    def test_is_finished_false_unless_finished(self, tournament_status) -> None:
        tournament = TournamentFactory(status=tournament_status)
        assert tournament.is_finished is False

    def test_is_finished_true_for_finished(self) -> None:
        tournament = TournamentFactory(status=Tournament.Status.FINISHED)
        assert tournament.is_finished is True


# ---------------------------------------------------------------------------
# TestTournamentRevertMethods
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTournamentRevertMethods:
    def test_revert_to_set_sets_status(self) -> None:
        tournament = TournamentFactory(status=Tournament.Status.STARTED)

        tournament.revert_to_set()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.SET

    def test_revert_to_started_sets_status(self) -> None:
        tournament = TournamentFactory(status=Tournament.Status.FINISHED)

        tournament.revert_to_started()

        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED


# ---------------------------------------------------------------------------
# TestSetStatusDiagnostics
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSetStatusDiagnostics:
    def test_all_conditions_met(self) -> None:
        tournament = _tournament_with_config()
        for i in range(4):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        diagnostics = tournament.set_status_diagnostics()

        assert diagnostics["is_set_ready"] is True
        assert diagnostics["missing_configuration"] is False
        assert diagnostics["missing_game_format"] is False
        assert diagnostics["pairs_count"] == 4
        assert diagnostics["pairs_without_weight"] == []
        assert diagnostics["players_without_ranking"] == []

    def test_missing_configuration(self) -> None:
        tournament = TournamentFactory(
            game_format=Tournament.GameFormat.B1,
            configuration=None,
        )
        for i in range(4):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        diagnostics = tournament.set_status_diagnostics()

        assert diagnostics["is_set_ready"] is False
        assert diagnostics["missing_configuration"] is True
        assert diagnostics["missing_game_format"] is False

    def test_missing_game_format(self) -> None:
        tournament = TournamentFactory(
            game_format="",
            configuration=Tournament.Configuration.TMC,
        )
        for i in range(4):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        diagnostics = tournament.set_status_diagnostics()

        assert diagnostics["is_set_ready"] is False
        assert diagnostics["missing_game_format"] is True
        assert diagnostics["missing_configuration"] is False

    def test_fewer_than_four_pairs(self) -> None:
        tournament = _tournament_with_config()
        for i in range(2):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        diagnostics = tournament.set_status_diagnostics()

        assert diagnostics["is_set_ready"] is False
        assert diagnostics["pairs_count"] == 2

    def test_pair_without_weight_reported_and_others_unaffected(self) -> None:
        tournament = _tournament_with_config()
        unweighted_pair = PairFactory(tournament=tournament, weight=None)
        for i in range(3):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        diagnostics = tournament.set_status_diagnostics()

        assert diagnostics["is_set_ready"] is False
        assert diagnostics["pairs_count"] == 4
        assert len(diagnostics["pairs_without_weight"]) == 1
        reported = diagnostics["pairs_without_weight"][0]
        assert reported["id"] == unweighted_pair.id
        assert reported["player1"] == str(unweighted_pair.player1)
        assert reported["player2"] == str(unweighted_pair.player2)

    def test_player_without_ranking_reported(self) -> None:
        tournament = _tournament_with_config()
        player_without_ranking = PlayerFactory(ranking=None)
        pair = PairFactory(
            tournament=tournament,
            weight=100.0,
            player1=player_without_ranking,
        )
        for i in range(3):
            PairFactory(tournament=tournament, weight=float(200 + i * 10))

        diagnostics = tournament.set_status_diagnostics()

        assert diagnostics["is_set_ready"] is False
        assert len(diagnostics["players_without_ranking"]) == 1
        reported = diagnostics["players_without_ranking"][0]
        assert reported["pair_id"] == pair.id
        assert reported["player_id"] == player_without_ranking.id
        assert (
            reported["full_name"]
            == f"{player_without_ranking.first_name} {player_without_ranking.last_name}"
        )

    def test_multiple_simultaneous_failures_are_all_reported(self) -> None:
        tournament = TournamentFactory(
            game_format="",
            configuration=None,
        )
        unweighted_pair = PairFactory(tournament=tournament, weight=None)
        for i in range(2):
            PairFactory(tournament=tournament, weight=float(100 + i * 10))

        diagnostics = tournament.set_status_diagnostics()

        assert diagnostics["is_set_ready"] is False
        assert diagnostics["missing_configuration"] is True
        assert diagnostics["missing_game_format"] is True
        assert diagnostics["pairs_count"] == 3
        assert len(diagnostics["pairs_without_weight"]) == 1
        assert diagnostics["pairs_without_weight"][0]["id"] == unweighted_pair.id
