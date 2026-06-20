import pytest
from rest_framework.test import APIClient

from apps.matches.models import Match
from apps.matches.services import generate_match_tree
from apps.matches.tests.factories import BracketFactory, MatchFactory
from apps.players.models import Pair
from apps.players.tests.factories import PairFactory
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory


def _score_url(tournament_id: int, match_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/matches/{match_id}/score/"


def _build_fully_scored_dim8_tree(
    authenticated_client: APIClient, tournament: Tournament
) -> dict:
    """Build a real dim=8 match tree and score every match bottom-up
    (quarts, then demies, then finale) through the actual PATCH endpoint,
    so propagation goes through `_propagate_winner` rather than being
    hand-rolled.

    Returns a dict with the finale, both demies, the 4 quarts, and the
    winner Pair chosen at each match, so individual tests can target one
    specific branch:
    {
        "finale": Match, "finale_winner": Pair,
        "demie1": Match, "demie1_winner": Pair,
        "demie2": Match, "demie2_winner": Pair,
        "quart1": Match, "quart1_winner": Pair,
        "quart2": Match, "quart2_winner": Pair,
        "quart3": Match, "quart3_winner": Pair,
        "quart4": Match, "quart4_winner": Pair,
    }

    `quart1`/`quart2` feed `demie1`; `quart3`/`quart4` feed `demie2`
    (mirroring `generate_match_tree`'s bottom-up pairing).
    """
    bracket = BracketFactory(tournament=tournament, dimension=8)
    finale = generate_match_tree(bracket, tournament.game_format)
    demie1, demie2 = Match.objects.filter(
        bracket=bracket, round="DEMIE_FINALE"
    ).order_by("match_number")
    quart1, quart2, quart3, quart4 = Match.objects.filter(
        bracket=bracket, round="QUART_DE_FINALE"
    ).order_by("match_number")

    quart_winners: dict[str, Pair] = {}
    for quart in (quart1, quart2, quart3, quart4):
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        quart.pair1 = pair1
        quart.pair2 = pair2
        quart.save(update_fields=["pair1", "pair2", "updated_at"])
        winner = pair1
        authenticated_client.patch(
            _score_url(tournament.pk, quart.pk),
            {"score": "6/4 6/4", "winner_id": winner.pk},
            format="json",
        )
        quart_winners[quart.pk] = winner

    for demie in (demie1, demie2):
        demie.refresh_from_db()

    demie1_winner = quart_winners[quart1.pk]
    authenticated_client.patch(
        _score_url(tournament.pk, demie1.pk),
        {"score": "6/3 6/3", "winner_id": demie1_winner.pk},
        format="json",
    )
    demie2_winner = quart_winners[quart3.pk]
    authenticated_client.patch(
        _score_url(tournament.pk, demie2.pk),
        {"score": "6/2 6/2", "winner_id": demie2_winner.pk},
        format="json",
    )

    finale.refresh_from_db()
    finale_winner = demie1_winner
    authenticated_client.patch(
        _score_url(tournament.pk, finale.pk),
        {"score": "6/1 6/1", "winner_id": finale_winner.pk},
        format="json",
    )

    finale.refresh_from_db()
    demie1.refresh_from_db()
    demie2.refresh_from_db()

    return {
        "finale": finale,
        "finale_winner": finale_winner,
        "demie1": demie1,
        "demie1_winner": demie1_winner,
        "demie2": demie2,
        "demie2_winner": demie2_winner,
        "quart1": quart1,
        "quart1_winner": quart_winners[quart1.pk],
        "quart2": quart2,
        "quart2_winner": quart_winners[quart2.pk],
        "quart3": quart3,
        "quart3_winner": quart_winners[quart3.pk],
        "quart4": quart4,
        "quart4_winner": quart_winners[quart4.pk],
    }


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

    def test_patch_sets_status_finished_and_finished_at(
        self, authenticated_client, tournament
    ):
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
        assert data["status"] == "FINISHED"
        assert data["finished_at"] is not None
        match.refresh_from_db()
        assert match.status == Match.Status.FINISHED
        assert match.finished_at is not None

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

    Dependency-based rule: a match's score can be deleted only if the match
    it feeds into (its "parent") does not already have a winner. The FINALE
    has no parent, so it can always be deleted. Deleting a match un-
    propagates its winner from the parent's pair slot. Tournament status is
    only ever affected by deleting the FINALE's score (reverts to STARTED);
    deleting any other match's score leaves tournament status untouched.
    """

    def test_204_deletes_final_score_and_reverts_to_started(
        self, authenticated_client, tournament
    ):
        tree = _build_fully_scored_dim8_tree(authenticated_client, tournament)
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

        resp = authenticated_client.delete(
            _score_url(tournament.pk, tree["finale"].pk)
        )

        assert resp.status_code == 204
        finale = tree["finale"]
        finale.refresh_from_db()
        assert finale.score == ""
        assert finale.winner is None
        assert finale.status == Match.Status.UPCOMING
        assert finale.finished_at is None
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

    def test_409_delete_demie_while_finale_has_winner(
        self, authenticated_client, tournament
    ):
        tree = _build_fully_scored_dim8_tree(authenticated_client, tournament)
        demie1 = tree["demie1"]

        resp = authenticated_client.delete(_score_url(tournament.pk, demie1.pk))

        assert resp.status_code == 409
        demie1.refresh_from_db()
        assert demie1.score != ""
        assert demie1.winner_id == tree["demie1_winner"].pk
        finale = tree["finale"]
        finale.refresh_from_db()
        assert finale.pair1_id == tree["demie1_winner"].pk

    def test_409_delete_quart_while_demie_has_winner(
        self, authenticated_client, tournament
    ):
        tree = _build_fully_scored_dim8_tree(authenticated_client, tournament)
        quart1 = tree["quart1"]

        resp = authenticated_client.delete(_score_url(tournament.pk, quart1.pk))

        assert resp.status_code == 409
        quart1.refresh_from_db()
        assert quart1.score != ""
        assert quart1.winner_id == tree["quart1_winner"].pk
        demie1 = tree["demie1"]
        demie1.refresh_from_db()
        assert demie1.pair1_id == tree["quart1_winner"].pk

    def test_204_delete_demie_after_finale_deleted_resets_finale_slot(
        self, authenticated_client, tournament
    ):
        tree = _build_fully_scored_dim8_tree(authenticated_client, tournament)
        finale = tree["finale"]
        demie1 = tree["demie1"]
        demie2_winner = tree["demie2_winner"]

        authenticated_client.delete(_score_url(tournament.pk, finale.pk))
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

        resp = authenticated_client.delete(_score_url(tournament.pk, demie1.pk))

        assert resp.status_code == 204
        demie1.refresh_from_db()
        assert demie1.score == ""
        assert demie1.winner is None
        finale.refresh_from_db()
        assert finale.pair1_id is None
        assert finale.pair2_id == demie2_winner.pk
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

    def test_204_delete_quart_after_demie_deleted_resets_demie_slot(
        self, authenticated_client, tournament
    ):
        tree = _build_fully_scored_dim8_tree(authenticated_client, tournament)
        finale = tree["finale"]
        demie1 = tree["demie1"]
        quart1 = tree["quart1"]
        quart2_winner = tree["quart2_winner"]

        authenticated_client.delete(_score_url(tournament.pk, finale.pk))
        authenticated_client.delete(_score_url(tournament.pk, demie1.pk))
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

        resp = authenticated_client.delete(_score_url(tournament.pk, quart1.pk))

        assert resp.status_code == 204
        quart1.refresh_from_db()
        assert quart1.score == ""
        assert quart1.winner is None
        demie1.refresh_from_db()
        assert demie1.pair1_id is None
        assert demie1.pair2_id == quart2_winner.pk
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

    def test_401_unauthenticated(self, client, tournament):
        bracket = BracketFactory(tournament=tournament, dimension=8)
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
        tree = _build_fully_scored_dim8_tree(authenticated_client, tournament)
        finale = tree["finale"]
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

        authenticated_client.delete(_score_url(tournament.pk, finale.pk))
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

        resp = authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "7/5 6/4", "winner_id": tree["demie2_winner"].pk},
            format="json",
        )

        assert resp.status_code == 200
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED
