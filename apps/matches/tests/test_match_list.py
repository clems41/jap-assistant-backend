from datetime import datetime, time
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.matches.models import Bracket, Match
from apps.tournaments.tests.factories import TimeSlotFactory, TournamentFactory
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
            "started_at",
            "finished_at",
            "estimated_start_at",
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


@pytest.mark.django_db
class TestMatchListEstimatedStartAt:
    def test_upcoming_match_gets_a_non_null_estimate_when_configurable(
        self, authenticated_client, tournament, bracket
    ):
        tournament.estimated_match_duration = 45
        tournament.save()
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(8, 0),
            end_time=time(23, 0),
            courts_available=4,
        )
        now = timezone.make_aware(datetime.combine(tournament.start_date, time(9, 0)))

        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        upcoming_payloads = [m for m in resp.json() if m["status"] == "UPCOMING"]
        assert upcoming_payloads
        for m in upcoming_payloads:
            assert m["estimated_start_at"] is not None

    def test_started_and_finished_matches_have_null_estimate(
        self, authenticated_client, tournament, bracket
    ):
        tournament.estimated_match_duration = 45
        tournament.save()
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(8, 0),
            end_time=time(23, 0),
            courts_available=4,
        )
        matches = list(Match.objects.filter(bracket=bracket).order_by("order"))
        started_match = matches[0]
        started_match.status = Match.Status.STARTED
        started_match.started_at = timezone.now()
        started_match.save()
        finished_match = matches[1]
        finished_match.status = Match.Status.FINISHED
        finished_match.score = "6/4 6/4"
        finished_match.finished_at = timezone.now()
        finished_match.save()

        now = timezone.make_aware(datetime.combine(tournament.start_date, time(9, 0)))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        payloads_by_id = {m["id"]: m for m in resp.json()}
        assert payloads_by_id[started_match.pk]["estimated_start_at"] is None
        assert payloads_by_id[finished_match.pk]["estimated_start_at"] is None

    def test_null_estimate_without_estimated_match_duration(
        self, authenticated_client, tournament, bracket
    ):
        tournament.estimated_match_duration = None
        tournament.save()
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(8, 0),
            end_time=time(23, 0),
            courts_available=4,
        )

        resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        upcoming_payloads = [m for m in resp.json() if m["status"] == "UPCOMING"]
        assert upcoming_payloads
        for m in upcoming_payloads:
            assert m["estimated_start_at"] is None

    def test_null_estimate_without_any_time_slot(
        self, authenticated_client, tournament, bracket
    ):
        tournament.estimated_match_duration = 45
        tournament.save()

        resp = authenticated_client.get(_list_url(tournament.pk))

        assert resp.status_code == 200
        upcoming_payloads = [m for m in resp.json() if m["status"] == "UPCOMING"]
        assert upcoming_payloads
        for m in upcoming_payloads:
            assert m["estimated_start_at"] is None

    def test_status_filter_does_not_change_underlying_simulation(
        self, authenticated_client, tournament, bracket
    ):
        tournament.estimated_match_duration = 45
        tournament.save()
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(8, 0),
            end_time=time(23, 0),
            courts_available=4,
        )
        now = timezone.make_aware(datetime.combine(tournament.start_date, time(9, 0)))

        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            full_resp = authenticated_client.get(_list_url(tournament.pk))
            filtered_resp = authenticated_client.get(
                _list_url(tournament.pk), {"status": "UPCOMING"}
            )

        full_estimates = {
            m["id"]: m["estimated_start_at"]
            for m in full_resp.json()
            if m["status"] == "UPCOMING"
        }
        filtered_estimates = {
            m["id"]: m["estimated_start_at"] for m in filtered_resp.json()
        }
        assert filtered_estimates == full_estimates
