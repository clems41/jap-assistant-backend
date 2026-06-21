import pytest
from rest_framework.test import APIClient

from apps.matches.models import Bracket, Match
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory


def _list_url(tournament_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/matches/"


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


@pytest.mark.django_db
class TestMatchListHappyPath:
    def test_returns_all_matches_ordered_by_order_field(
        self, authenticated_client, tournament, bracket
    ):
        resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        expected_ids = list(
            Match.objects.filter(bracket=bracket)
            .order_by("order")
            .values_list("pk", flat=True)
        )
        assert [m["id"] for m in resp.json()] == expected_ids

    def test_response_is_a_plain_array_not_paginated(
        self, authenticated_client, tournament, bracket
    ):
        resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_match_payload_has_no_child_fields(
        self, authenticated_client, tournament, bracket
    ):
        resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        payload = resp.json()[0]
        assert set(payload.keys()) == {
            "id",
            "round",
            "round_display",
            "match_number",
            "order",
            "pair1",
            "pair2",
            "winner_id",
            "game_format",
            "score",
            "status",
            "status_display",
            "finished_at",
        }

    def test_empty_array_when_no_bracket_generated_yet(
        self, authenticated_client, tournament
    ):
        resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        assert resp.json() == []

    def test_disabled_matches_are_excluded(
        self, authenticated_client, tournament, bracket
    ):
        match = Match.objects.filter(bracket=bracket).first()
        match.disabled = True
        match.save()

        resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        assert match.pk not in [m["id"] for m in resp.json()]


@pytest.mark.django_db
class TestMatchListStatusFilter:
    def test_filter_by_single_status(self, authenticated_client, tournament, bracket):
        match = Match.objects.filter(bracket=bracket).first()
        match.status = Match.Status.STARTED
        match.save()

        resp = authenticated_client.get(_list_url(tournament.pk), {"status": "STARTED"})

        assert resp.status_code == 200
        assert [m["id"] for m in resp.json()] == [match.pk]

    def test_filter_by_multiple_statuses_via_repeated_param(
        self, authenticated_client, tournament, bracket
    ):
        matches = list(Match.objects.filter(bracket=bracket).order_by("order"))
        started_match = matches[0]
        started_match.status = Match.Status.STARTED
        started_match.save()

        finished_match = matches[1]
        finished_match.status = Match.Status.FINISHED
        finished_match.score = "6-4 6-3"
        finished_match.save()

        url = f"{_list_url(tournament.pk)}?status=STARTED&status=FINISHED"
        resp = authenticated_client.get(url)

        assert resp.status_code == 200
        returned_ids = {m["id"] for m in resp.json()}
        assert returned_ids == {started_match.pk, finished_match.pk}

    def test_no_status_filter_returns_all_statuses(
        self, authenticated_client, tournament, bracket
    ):
        resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        expected_count = Match.objects.filter(bracket=bracket, disabled=False).count()
        assert len(resp.json()) == expected_count


@pytest.mark.django_db
class TestMatchListIsolationAndAuth:
    def test_other_tournaments_matches_are_not_affected(
        self, authenticated_client, tournament, bracket, user
    ):
        other_tournament = TournamentFactory(owner=user)
        other_bracket = Bracket.objects.create(tournament=other_tournament, dimension=2)
        other_match = Match.objects.create(
            bracket=other_bracket, round="FINALE", match_number=1
        )

        resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        assert other_match.pk not in [m["id"] for m in resp.json()]

    def test_401_unauthenticated(self, tournament, bracket):
        anon = APIClient()

        resp = anon.get(_list_url(tournament.pk))

        assert resp.status_code == 401

    def test_404_non_owner(self, tournament, bracket):
        other = UserFactory()
        other_client = APIClient()
        other_client.force_authenticate(user=other)

        resp = other_client.get(_list_url(tournament.pk))

        assert resp.status_code == 404
