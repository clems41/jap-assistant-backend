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
