import pytest
from rest_framework.test import APIClient

from apps.matches.models import Bracket, Match
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory


def _order_url(tournament_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/matches/order/"


def _zero_seeding() -> dict:
    return {
        "nb_pair_round_64": 0,
        "nb_pair_round_32": 0,
        "nb_pair_round_16": 0,
        "nb_pair_round_8": 0,
        "nb_pair_round_4": 0,
    }


@pytest.fixture
def bracket(authenticated_client, tournament):
    authenticated_client.post(
        f"/api/v1/tournaments/{tournament.pk}/bracket/",
        {"dimension": 8, **_zero_seeding()},
        format="json",
    )
    return Bracket.objects.get(tournament=tournament)


@pytest.fixture
def upcoming_matches(bracket):
    """All matches of the dim=8 bracket are UPCOMING right after generation
    (no scores entered yet) — 7 matches total (4 QUART + 2 DEMIE + 1 FINALE).
    """
    return list(Match.objects.filter(bracket=bracket).order_by("order"))


@pytest.mark.django_db
class TestMatchReorderHappyPath:
    def test_reorder_persists_order_per_position(
        self, authenticated_client, tournament, upcoming_matches
    ):
        match_ids = [m.pk for m in reversed(upcoming_matches)]

        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 200
        for index, match_id in enumerate(match_ids):
            match = Match.objects.get(pk=match_id)
            assert match.order == index + 1

    def test_response_is_matches_in_request_order(
        self, authenticated_client, tournament, upcoming_matches
    ):
        match_ids = [m.pk for m in reversed(upcoming_matches)]

        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert [m["id"] for m in data] == match_ids
        assert [m["order"] for m in data] == list(range(1, len(match_ids) + 1))

    def test_other_tournament_matches_are_not_affected(
        self, authenticated_client, tournament, upcoming_matches, user
    ):
        other_tournament = TournamentFactory(owner=user)
        other_bracket = Bracket.objects.create(tournament=other_tournament, dimension=2)
        other_match = Match.objects.create(
            bracket=other_bracket, round="FINALE", match_number=1, order=99
        )

        match_ids = [m.pk for m in reversed(upcoming_matches)]
        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 200
        other_match.refresh_from_db()
        assert other_match.order == 99

    def test_finished_matches_are_not_touched_or_required(
        self, authenticated_client, tournament, upcoming_matches
    ):
        """A match that already has a score (FINISHED) is excluded from the
        UPCOMING set: it must neither be required in the payload nor have
        its order changed by this endpoint."""
        finished_match = upcoming_matches[0]
        finished_match.status = Match.Status.FINISHED
        finished_match.score = "6-4 6-3"
        finished_match.order = 123
        finished_match.save()

        remaining_upcoming = list(upcoming_matches[1:])
        match_ids = [m.pk for m in reversed(remaining_upcoming)]

        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 200
        finished_match.refresh_from_db()
        assert finished_match.order == 123


@pytest.mark.django_db
class TestMatchReorderValidation:
    def test_400_duplicate_id_in_list(
        self, authenticated_client, tournament, upcoming_matches
    ):
        match_ids = [m.pk for m in upcoming_matches]
        match_ids[1] = match_ids[0]

        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 400

    def test_400_unknown_id(self, authenticated_client, tournament, upcoming_matches):
        match_ids = [m.pk for m in upcoming_matches]
        match_ids[0] = 999999

        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 400

    def test_400_id_from_another_tournament(
        self, authenticated_client, tournament, upcoming_matches, user
    ):
        other_tournament = TournamentFactory(owner=user)
        other_bracket = Bracket.objects.create(tournament=other_tournament, dimension=2)
        other_match = Match.objects.create(
            bracket=other_bracket, round="FINALE", match_number=1
        )

        match_ids = [m.pk for m in upcoming_matches]
        match_ids[0] = other_match.pk

        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 400

    def test_400_non_upcoming_id_included(
        self, authenticated_client, tournament, upcoming_matches
    ):
        finished_match = upcoming_matches[0]
        finished_match.status = Match.Status.FINISHED
        finished_match.score = "6-4 6-3"
        finished_match.save()

        match_ids = [m.pk for m in upcoming_matches]  # includes the finished one

        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 400

    def test_400_missing_upcoming_id(
        self, authenticated_client, tournament, upcoming_matches
    ):
        match_ids = [m.pk for m in upcoming_matches[:-1]]  # one missing

        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 400

    def test_400_empty_list_while_upcoming_matches_exist(
        self, authenticated_client, tournament, upcoming_matches
    ):
        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": []}, format="json"
        )

        assert resp.status_code == 400


@pytest.mark.django_db
class TestMatchReorderAuthAndState:
    def test_401_unauthenticated(self, tournament, upcoming_matches):
        anon = APIClient()
        match_ids = [m.pk for m in upcoming_matches]

        resp = anon.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 401

    def test_404_non_owner(self, tournament, upcoming_matches):
        other = UserFactory()
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        match_ids = [m.pk for m in upcoming_matches]

        resp = other_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 404

    def test_409_when_tournament_finished(
        self, authenticated_client, tournament, upcoming_matches
    ):
        tournament.status = Tournament.Status.FINISHED
        tournament.save()
        match_ids = [m.pk for m in upcoming_matches]

        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 409

    def test_200_when_tournament_started(
        self, authenticated_client, tournament, upcoming_matches
    ):
        tournament.status = Tournament.Status.STARTED
        tournament.save()
        match_ids = [m.pk for m in reversed(upcoming_matches)]

        resp = authenticated_client.patch(
            _order_url(tournament.pk), {"match_ids": match_ids}, format="json"
        )

        assert resp.status_code == 200
