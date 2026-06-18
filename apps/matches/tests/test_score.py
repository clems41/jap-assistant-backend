import pytest

from apps.matches.tests.factories import BracketFactory, MatchFactory
from apps.players.tests.factories import PairFactory
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory


def _score_url(tournament_id: int, match_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/matches/{match_id}/score/"


@pytest.mark.django_db
class TestMatchScorePatch:
    def test_patch_score_with_pair1_as_winner(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE")

        resp = authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == "6/4 7/5"
        assert data["winner_id"] == pair1.pk

    def test_patch_score_with_pair2_as_winner(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE")

        resp = authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "3/6 6/4 10/8", "winner_id": pair2.pk},
            format="json",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == "3/6 6/4 10/8"
        assert data["winner_id"] == pair2.pk

    def test_400_winner_id_not_pair1_or_pair2(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        other_pair = PairFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE")

        resp = authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4 7/5", "winner_id": other_pair.pk},
            format="json",
        )

        assert resp.status_code == 400

    def test_400_match_without_pairs(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=None, pair2=None, round="FINALE")

        pair = PairFactory(tournament=tournament)
        resp = authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4", "winner_id": pair.pk},
            format="json",
        )

        assert resp.status_code == 400

    def test_401_unauthenticated(self, client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=pair1, pair2=pair2)

        resp = client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 401

    def test_404_match_from_another_tournament(
        self, authenticated_client, tournament, user
    ):
        other_tournament = TournamentFactory(owner=user)
        other_bracket = BracketFactory(tournament=other_tournament)
        pair1 = PairFactory(tournament=other_tournament)
        pair2 = PairFactory(tournament=other_tournament)
        other_match = MatchFactory(bracket=other_bracket, pair1=pair1, pair2=pair2)

        resp = authenticated_client.patch(
            _score_url(tournament.pk, other_match.pk),
            {"score": "6/4", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 404

    def test_propagation_winner_becomes_pair1_of_parent(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)

        child_match = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="DEMIE_FINALE",
            match_number=1,
        )
        parent_match = MatchFactory(
            bracket=bracket, round="FINALE", match_number=1, child1=child_match
        )

        resp = authenticated_client.patch(
            _score_url(tournament.pk, child_match.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 200
        parent_match.refresh_from_db()
        assert parent_match.pair1_id == pair1.pk

    def test_propagation_winner_becomes_pair2_of_parent(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)

        child_match = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="DEMIE_FINALE",
            match_number=2,
        )
        parent_match = MatchFactory(
            bracket=bracket, round="FINALE", match_number=1, child2=child_match
        )

        resp = authenticated_client.patch(
            _score_url(tournament.pk, child_match.pk),
            {"score": "6/4 7/5", "winner_id": pair2.pk},
            format="json",
        )

        assert resp.status_code == 200
        parent_match.refresh_from_db()
        assert parent_match.pair2_id == pair2.pk

    def test_finale_no_parent_returns_200(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        finale = MatchFactory(
            bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE", match_number=1
        )

        resp = authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 200

    def test_400_match_is_disabled(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(
            bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE", disabled=True
        )

        resp = authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 400

    def test_winner_persisted_in_db(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE")

        authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )

        match.refresh_from_db()
        assert match.winner_id == pair1.pk
        assert match.score == "6/4 7/5"

    def test_409_patch_non_finale_match_when_tournament_finished(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="DEMIE_FINALE",
            match_number=1,
        )
        tournament.status = Tournament.Status.FINISHED
        tournament.save()

        resp = authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 409
        match.refresh_from_db()
        assert match.score == ""


@pytest.mark.django_db
class TestMatchScoreTournamentStatus:
    def test_first_score_on_non_finale_match_starts_tournament(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)

        child_match = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="DEMIE_FINALE",
            match_number=1,
        )
        MatchFactory(
            bracket=bracket, round="FINALE", match_number=1, child1=child_match
        )

        resp = authenticated_client.patch(
            _score_url(tournament.pk, child_match.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 200
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

    def test_second_score_keeps_tournament_started(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        pair3 = PairFactory(tournament=tournament)
        pair4 = PairFactory(tournament=tournament)

        match1 = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="DEMIE_FINALE",
            match_number=1,
        )
        match2 = MatchFactory(
            bracket=bracket,
            pair1=pair3,
            pair2=pair4,
            round="DEMIE_FINALE",
            match_number=2,
        )
        MatchFactory(
            bracket=bracket,
            round="FINALE",
            match_number=1,
            child1=match1,
            child2=match2,
        )

        authenticated_client.patch(
            _score_url(tournament.pk, match1.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

        resp = authenticated_client.patch(
            _score_url(tournament.pk, match2.pk),
            {"score": "6/2 6/3", "winner_id": pair3.pk},
            format="json",
        )

        assert resp.status_code == 200
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

    def test_score_on_finale_match_finishes_tournament(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        finale = MatchFactory(
            bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE", match_number=1
        )

        resp = authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 200
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

    def test_score_on_non_finale_match_does_not_finish_tournament(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)

        child_match = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="DEMIE_FINALE",
            match_number=1,
        )
        MatchFactory(
            bracket=bracket, round="FINALE", match_number=1, child1=child_match
        )

        resp = authenticated_client.patch(
            _score_url(tournament.pk, child_match.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 200
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED
        assert tournament.status != Tournament.Status.FINISHED

    def test_resubmitting_finale_score_keeps_tournament_finished(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        finale = MatchFactory(
            bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE", match_number=1
        )

        resp1 = authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )
        assert resp1.status_code == 200
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

        resp2 = authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "4/6 6/4 10/8", "winner_id": pair2.pk},
            format="json",
        )

        assert resp2.status_code == 200
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

    def test_rejected_score_does_not_change_tournament_status(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(
            bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE", disabled=True
        )

        resp = authenticated_client.patch(
            _score_url(tournament.pk, match.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 400
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.DRAFT


@pytest.mark.django_db
class TestMatchScoreDelete:
    """DELETE /tournaments/{id}/matches/{match_id}/score/

    Deliberately narrow scope: the only allowed case is correcting the
    final's score once the tournament is FINISHED (which reverts it to
    STARTED). Every other combination must return 409.
    """

    @staticmethod
    def _finished_tournament_with_untouched_semifinal(tournament):
        """Build an 8-dimension bracket where only the finale has been
        scored (reaching FINISHED), leaving one semi-final match
        unscored/untouched.

        MatchScoreSerializer.validate() does not require child matches to
        already have scores before the final can be scored — it only checks
        the match isn't disabled and both pairs are defined. So scoring only
        the finale directly (bypass-placing pairs into it) is sufficient.
        """
        bracket = BracketFactory(tournament=tournament, dimension=8, nb_top_seeds=2)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        finale = MatchFactory(
            bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE", match_number=1
        )
        untouched_semifinal = MatchFactory(
            bracket=bracket, round="DEMIE_FINALE", match_number=1
        )
        tournament.status = Tournament.Status.STARTED
        tournament.save()
        return finale, pair1, pair2, untouched_semifinal

    def test_204_deletes_final_score_and_reverts_to_started(
        self, authenticated_client, tournament
    ):
        finale, pair1, pair2, _ = self._finished_tournament_with_untouched_semifinal(
            tournament
        )
        authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

        resp = authenticated_client.delete(_score_url(tournament.pk, finale.pk))

        assert resp.status_code == 204
        finale.refresh_from_db()
        assert finale.score == ""
        assert finale.winner is None
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

    def test_409_delete_non_finale_match_while_finished(
        self, authenticated_client, tournament
    ):
        finale, pair1, pair2, untouched_semifinal = (
            self._finished_tournament_with_untouched_semifinal(tournament)
        )
        authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

        resp = authenticated_client.delete(
            _score_url(tournament.pk, untouched_semifinal.pk)
        )

        assert resp.status_code == 409

    def test_409_delete_final_while_started(self, authenticated_client, tournament):
        """Defensive/edge-case test: construct a STARTED tournament with a
        scored final directly (bypassing the normal PATCH flow, which would
        have moved the tournament to FINISHED), to confirm the guard checks
        BOTH conditions (tournament.is_finished AND match.round == FINALE)
        rather than relying on the normal invariant that a scored final
        implies FINISHED."""
        bracket = BracketFactory(tournament=tournament, dimension=8, nb_top_seeds=2)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        finale = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="FINALE",
            match_number=1,
            score="6/4 7/5",
            winner=pair1,
        )
        tournament.status = Tournament.Status.STARTED
        tournament.save()

        resp = authenticated_client.delete(_score_url(tournament.pk, finale.pk))

        assert resp.status_code == 409
        finale.refresh_from_db()
        assert finale.score == "6/4 7/5"

    @pytest.mark.parametrize(
        "tournament_status", [Tournament.Status.DRAFT, Tournament.Status.SET]
    )
    def test_409_delete_final_while_not_started_or_finished(
        self, authenticated_client, tournament, tournament_status
    ):
        bracket = BracketFactory(tournament=tournament, dimension=8, nb_top_seeds=2)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        finale = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="FINALE",
            match_number=1,
            score="6/4 7/5",
            winner=pair1,
        )
        tournament.status = tournament_status
        tournament.save()

        resp = authenticated_client.delete(_score_url(tournament.pk, finale.pk))

        assert resp.status_code == 409

    def test_409_delete_non_finale_match_while_started(
        self, authenticated_client, tournament
    ):
        """No general delete-while-STARTED feature: a non-final match's
        score cannot be deleted even while the tournament is STARTED."""
        bracket = BracketFactory(tournament=tournament, dimension=8, nb_top_seeds=2)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="DEMIE_FINALE",
            match_number=1,
            score="6/4 7/5",
            winner=pair1,
        )
        tournament.status = Tournament.Status.STARTED
        tournament.save()

        resp = authenticated_client.delete(_score_url(tournament.pk, match.pk))

        assert resp.status_code == 409

    def test_401_unauthenticated(self, client, tournament):
        bracket = BracketFactory(tournament=tournament, dimension=8, nb_top_seeds=2)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        finale = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="FINALE",
            match_number=1,
            score="6/4 7/5",
            winner=pair1,
        )
        tournament.status = Tournament.Status.FINISHED
        tournament.save()

        resp = client.delete(_score_url(tournament.pk, finale.pk))

        assert resp.status_code == 401

    def test_404_match_from_another_tournament(
        self, authenticated_client, tournament, user
    ):
        other_tournament = TournamentFactory(owner=user)
        other_bracket = BracketFactory(tournament=other_tournament)
        pair1 = PairFactory(tournament=other_tournament)
        pair2 = PairFactory(tournament=other_tournament)
        other_match = MatchFactory(bracket=other_bracket, pair1=pair1, pair2=pair2)

        resp = authenticated_client.delete(_score_url(tournament.pk, other_match.pk))

        assert resp.status_code == 404

    def test_round_trip_delete_then_repatch_refinishes_tournament(
        self, authenticated_client, tournament
    ):
        finale, pair1, pair2, _ = self._finished_tournament_with_untouched_semifinal(
            tournament
        )
        authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "6/4 7/5", "winner_id": pair1.pk},
            format="json",
        )
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

        authenticated_client.delete(_score_url(tournament.pk, finale.pk))
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

        resp = authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "7/5 6/4", "winner_id": pair2.pk},
            format="json",
        )

        assert resp.status_code == 200
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED
