import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.matches.models import Match
from apps.matches.tests.factories import BracketFactory, MatchFactory
from apps.players.tests.factories import PairFactory
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory


def _start_url(tournament_id: int, match_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/matches/{match_id}/start/"


@pytest.mark.django_db
class TestMatchStart:
    def test_200_starts_upcoming_match_with_both_pairs(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE")

        resp = authenticated_client.post(_start_url(tournament.pk, match.pk))

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "STARTED"
        match.refresh_from_db()
        assert match.status == Match.Status.STARTED

    def test_200_sets_started_at(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE")

        before = timezone.now()
        resp = authenticated_client.post(_start_url(tournament.pk, match.pk))
        after = timezone.now()

        assert resp.status_code == 200
        data = resp.json()
        assert data["started_at"] is not None
        match.refresh_from_db()
        assert match.started_at is not None
        assert before <= match.started_at <= after

    def test_409_already_started(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="FINALE",
            status=Match.Status.STARTED,
        )

        resp = authenticated_client.post(_start_url(tournament.pk, match.pk))

        assert resp.status_code == 409
        match.refresh_from_db()
        assert match.status == Match.Status.STARTED

    def test_409_already_finished(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="FINALE",
            status=Match.Status.FINISHED,
        )

        resp = authenticated_client.post(_start_url(tournament.pk, match.pk))

        assert resp.status_code == 409
        match.refresh_from_db()
        assert match.status == Match.Status.FINISHED

    def test_409_match_disabled(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(
            bracket=bracket,
            pair1=pair1,
            pair2=pair2,
            round="FINALE",
            disabled=True,
        )

        resp = authenticated_client.post(_start_url(tournament.pk, match.pk))

        assert resp.status_code == 409
        match.refresh_from_db()
        assert match.status == Match.Status.UPCOMING

    def test_409_pair1_missing(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=None, pair2=pair2, round="FINALE")

        resp = authenticated_client.post(_start_url(tournament.pk, match.pk))

        assert resp.status_code == 409
        match.refresh_from_db()
        assert match.status == Match.Status.UPCOMING

    def test_409_pair2_missing(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=pair1, pair2=None, round="FINALE")

        resp = authenticated_client.post(_start_url(tournament.pk, match.pk))

        assert resp.status_code == 409
        match.refresh_from_db()
        assert match.status == Match.Status.UPCOMING

    def test_409_both_pairs_missing(self, authenticated_client, tournament):
        bracket = BracketFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=None, pair2=None, round="FINALE")

        resp = authenticated_client.post(_start_url(tournament.pk, match.pk))

        assert resp.status_code == 409
        match.refresh_from_db()
        assert match.status == Match.Status.UPCOMING

    def test_409_tournament_finished_and_match_not_finale(
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

        resp = authenticated_client.post(_start_url(tournament.pk, match.pk))

        assert resp.status_code == 409
        match.refresh_from_db()
        assert match.status == Match.Status.UPCOMING

    def test_401_unauthenticated(self, client: APIClient, tournament):
        bracket = BracketFactory(tournament=tournament)
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        match = MatchFactory(bracket=bracket, pair1=pair1, pair2=pair2, round="FINALE")

        resp = client.post(_start_url(tournament.pk, match.pk))

        assert resp.status_code == 401

    def test_404_match_from_another_tournament(
        self, authenticated_client, tournament, user
    ):
        other_tournament = TournamentFactory(owner=user)
        other_bracket = BracketFactory(tournament=other_tournament)
        pair1 = PairFactory(tournament=other_tournament)
        pair2 = PairFactory(tournament=other_tournament)
        other_match = MatchFactory(bracket=other_bracket, pair1=pair1, pair2=pair2)

        resp = authenticated_client.post(_start_url(tournament.pk, other_match.pk))

        assert resp.status_code == 404
