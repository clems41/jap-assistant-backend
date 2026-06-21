from datetime import datetime, time
from unittest import mock

import pytest
from django.utils import timezone

from apps.matches.models import Match
from apps.matches.services import compute_estimated_start_times
from apps.matches.tests.factories import BracketFactory, MatchFactory
from apps.tournaments.tests.factories import TimeSlotFactory, TournamentFactory


@pytest.mark.django_db
class TestComputeEstimatedStartTimesNoEstimationPossible:
    def test_no_estimated_match_duration_returns_empty_dict(self):
        tournament = TournamentFactory(estimated_match_duration=None)
        bracket = BracketFactory(tournament=tournament)
        MatchFactory(bracket=bracket, order=1, status=Match.Status.UPCOMING)

        result = compute_estimated_start_times(tournament)

        assert result == {}

    def test_no_time_slot_returns_empty_dict(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        bracket = BracketFactory(tournament=tournament)
        MatchFactory(bracket=bracket, order=1, status=Match.Status.UPCOMING)

        result = compute_estimated_start_times(tournament)

        assert result == {}


def _aware(d, t: time):
    return timezone.make_aware(datetime.combine(d, t))


@pytest.mark.django_db
class TestComputeEstimatedStartTimesReferenceExample:
    def test_four_waves_with_three_then_five_courts(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(12, 0),
            end_time=time(13, 30),
            courts_available=3,
        )
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(13, 30),
            end_time=time(20, 0),
            courts_available=5,
        )
        bracket = BracketFactory(tournament=tournament)
        matches = [
            MatchFactory(
                bracket=bracket, order=i, status=Match.Status.UPCOMING, round="FINALE"
            )
            for i in range(1, 17)
        ]

        now = _aware(tournament.start_date, time(11, 0))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        wave1 = _aware(tournament.start_date, time(12, 0))
        wave2 = _aware(tournament.start_date, time(12, 45))
        wave3 = _aware(tournament.start_date, time(13, 30))
        wave4 = _aware(tournament.start_date, time(14, 15))

        for m in matches[0:3]:
            assert result[m.id] == wave1
        for m in matches[3:6]:
            assert result[m.id] == wave2
        for m in matches[6:11]:
            assert result[m.id] == wave3
        for m in matches[11:16]:
            assert result[m.id] == wave4


@pytest.mark.django_db
class TestComputeEstimatedStartTimesWithStartedMatches:
    def test_started_match_with_known_started_at_reduces_first_wave_capacity(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(12, 0),
            end_time=time(20, 0),
            courts_available=3,
        )
        bracket = BracketFactory(tournament=tournament)

        started_at = _aware(tournament.start_date, time(11, 50))
        started_match = MatchFactory(
            bracket=bracket,
            order=1,
            status=Match.Status.STARTED,
            started_at=started_at,
            round="FINALE",
        )
        upcoming_matches = [
            MatchFactory(
                bracket=bracket, order=i, status=Match.Status.UPCOMING, round="FINALE"
            )
            for i in range(2, 6)
        ]

        now = _aware(tournament.start_date, time(11, 0))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        # Only 2 free courts remain at 12h00 (3 total - 1 occupied by
        # the STARTED match), so only 2 matches can start at the wave start.
        wave1_start = _aware(tournament.start_date, time(12, 0))
        assert result[upcoming_matches[0].id] == wave1_start
        assert result[upcoming_matches[1].id] == wave1_start

        # The 3rd court (occupied by the STARTED match) frees at
        # started_at + duration + COURT_CHANGEOVER = 11h50 + 45min + 5min.
        third_release = _aware(tournament.start_date, time(12, 40))
        assert result[upcoming_matches[2].id] == third_release

        assert started_match.id not in result

    def test_started_match_without_started_at_falls_back_to_effective_now(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(12, 0),
            end_time=time(20, 0),
            courts_available=1,
        )
        bracket = BracketFactory(tournament=tournament)

        MatchFactory(
            bracket=bracket,
            order=1,
            status=Match.Status.STARTED,
            started_at=None,
            round="FINALE",
        )
        upcoming_match = MatchFactory(
            bracket=bracket, order=2, status=Match.Status.UPCOMING, round="FINALE"
        )

        now = _aware(tournament.start_date, time(11, 0))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        # Defensive fallback: STARTED match without started_at is assumed
        # to have started at effective_now, so the only court frees at
        # effective_now + duration + COURT_CHANGEOVER = 12h00 + 45min + 5min.
        fallback_release = _aware(tournament.start_date, time(12, 50))
        assert result[upcoming_match.id] == fallback_release


@pytest.mark.django_db
class TestComputeEstimatedStartTimesWithFinishedMatches:
    def test_recent_finished_match_frees_a_court_earlier_with_changeover(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(12, 0),
            end_time=time(20, 0),
            courts_available=1,
        )
        bracket = BracketFactory(tournament=tournament)

        finished_at = _aware(tournament.start_date, time(12, 30))
        MatchFactory(
            bracket=bracket,
            order=1,
            status=Match.Status.FINISHED,
            finished_at=finished_at,
            score="6/4 6/4",
            round="FINALE",
        )
        upcoming_match = MatchFactory(
            bracket=bracket, order=2, status=Match.Status.UPCOMING, round="FINALE"
        )

        now = _aware(tournament.start_date, time(12, 31))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        expected = _aware(tournament.start_date, time(12, 35))
        assert result[upcoming_match.id] == expected

    def test_fewer_finished_matches_than_free_courts_are_free_immediately(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(12, 0),
            end_time=time(20, 0),
            courts_available=3,
        )
        bracket = BracketFactory(tournament=tournament)

        finished_at = _aware(tournament.start_date, time(12, 10))
        MatchFactory(
            bracket=bracket,
            order=1,
            status=Match.Status.FINISHED,
            finished_at=finished_at,
            score="6/4 6/4",
            round="FINALE",
        )
        upcoming_matches = [
            MatchFactory(
                bracket=bracket, order=i, status=Match.Status.UPCOMING, round="FINALE"
            )
            for i in range(2, 5)
        ]

        now = _aware(tournament.start_date, time(12, 15))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        # 1 court freed at 12h10 + 5min changeover = 12h15 (== now).
        # The other 2 courts have no known occupant: free immediately at
        # effective_now (12h00, but clamped to `now`=12h15 since estimates
        # are never in the past).
        assert result[upcoming_matches[0].id] == now
        assert result[upcoming_matches[1].id] == now
        assert result[upcoming_matches[2].id] == now


@pytest.mark.django_db
class TestComputeEstimatedStartTimesGapsAndCapacityLimits:
    def test_now_in_a_gap_between_two_slots_jumps_to_next_slot(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(9, 0),
            end_time=time(10, 0),
            courts_available=2,
        )
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(13, 0),
            end_time=time(20, 0),
            courts_available=4,
        )
        bracket = BracketFactory(tournament=tournament)
        upcoming_match = MatchFactory(
            bracket=bracket, order=1, status=Match.Status.UPCOMING, round="FINALE"
        )

        # now falls in the gap between the two slots (10h00-13h00).
        now = _aware(tournament.start_date, time(11, 0))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        expected = _aware(tournament.start_date, time(13, 0))
        assert result[upcoming_match.id] == expected

    def test_now_before_first_slot_jumps_to_first_slot(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(12, 0),
            end_time=time(20, 0),
            courts_available=2,
        )
        bracket = BracketFactory(tournament=tournament)
        upcoming_match = MatchFactory(
            bracket=bracket, order=1, status=Match.Status.UPCOMING, round="FINALE"
        )

        now = _aware(tournament.start_date, time(8, 0))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        expected = _aware(tournament.start_date, time(12, 0))
        assert result[upcoming_match.id] == expected

    def test_matches_beyond_scheduled_capacity_have_no_estimation(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(12, 0),
            end_time=time(13, 0),
            courts_available=1,
        )
        bracket = BracketFactory(tournament=tournament)
        # Slot is 1h wide with 1 court and 45min matches: the 1st match
        # starts at 12h00, the 2nd at 12h45 (still < the slot's end,
        # 13h00), but the 3rd would have to start at 13h30 — at/after the
        # slot's end with no further capacity scheduled for the day, so it
        # (and any match after it) gets no estimation.
        matches = [
            MatchFactory(
                bracket=bracket, order=i, status=Match.Status.UPCOMING, round="FINALE"
            )
            for i in range(1, 4)
        ]

        now = _aware(tournament.start_date, time(11, 0))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        assert matches[0].id in result
        assert matches[1].id in result
        assert matches[2].id not in result


@pytest.mark.django_db
class TestComputeEstimatedStartTimesDisabledMatches:
    def test_disabled_upcoming_matches_are_ignored(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(12, 0),
            end_time=time(20, 0),
            courts_available=1,
        )
        bracket = BracketFactory(tournament=tournament)
        disabled_match = MatchFactory(
            bracket=bracket,
            order=1,
            status=Match.Status.UPCOMING,
            round="FINALE",
            disabled=True,
        )
        upcoming_match = MatchFactory(
            bracket=bracket, order=2, status=Match.Status.UPCOMING, round="FINALE"
        )

        now = _aware(tournament.start_date, time(11, 0))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        assert disabled_match.id not in result
        expected = _aware(tournament.start_date, time(12, 0))
        assert result[upcoming_match.id] == expected

    def test_disabled_started_match_does_not_occupy_a_court(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(12, 0),
            end_time=time(20, 0),
            courts_available=1,
        )
        bracket = BracketFactory(tournament=tournament)
        MatchFactory(
            bracket=bracket,
            order=1,
            status=Match.Status.STARTED,
            started_at=_aware(tournament.start_date, time(11, 55)),
            round="FINALE",
            disabled=True,
        )
        upcoming_match = MatchFactory(
            bracket=bracket, order=2, status=Match.Status.UPCOMING, round="FINALE"
        )

        now = _aware(tournament.start_date, time(11, 0))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        # The disabled STARTED match must not occupy the only court: the
        # upcoming match should start right at the slot opening (12h00),
        # not wait for the disabled match's would-be release.
        expected = _aware(tournament.start_date, time(12, 0))
        assert result[upcoming_match.id] == expected

    def test_disabled_finished_match_does_not_count_as_a_recent_occupant(self):
        tournament = TournamentFactory(estimated_match_duration=45)
        TimeSlotFactory(
            tournament=tournament,
            start_time=time(12, 0),
            end_time=time(20, 0),
            courts_available=1,
        )
        bracket = BracketFactory(tournament=tournament)
        MatchFactory(
            bracket=bracket,
            order=1,
            status=Match.Status.FINISHED,
            finished_at=_aware(tournament.start_date, time(12, 10)),
            score="6/4 6/4",
            round="FINALE",
            disabled=True,
        )
        upcoming_match = MatchFactory(
            bracket=bracket, order=2, status=Match.Status.UPCOMING, round="FINALE"
        )

        now = _aware(tournament.start_date, time(12, 15))
        with mock.patch("apps.matches.services.timezone.now", return_value=now):
            result = compute_estimated_start_times(tournament)

        # The disabled FINISHED match's finished_at must be ignored: the
        # court is considered free since effective_now (12h00), clamped to
        # `now` (12h15) since estimates are never in the past.
        assert result[upcoming_match.id] == now
