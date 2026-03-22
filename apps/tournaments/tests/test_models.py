import pytest

from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory


@pytest.mark.django_db
class TestTournamentModel:
    def test_create_tournament_with_all_fields(self) -> None:
        tournament = TournamentFactory(
            name="Open Sud",
            category=Tournament.Category.P100,
            start_date="2026-06-15",
            location="Marseille",
            league=Tournament.League.PROVENCE_ALPES_COTES_AZUR,
            gender=Tournament.Gender.MIXED,
        )
        assert tournament.pk is not None
        assert tournament.name == "Open Sud"
        assert tournament.category == Tournament.Category.P100
        assert str(tournament.start_date) == "2026-06-15"
        assert tournament.location == "Marseille"
        assert tournament.league == Tournament.League.PROVENCE_ALPES_COTES_AZUR
        assert tournament.gender == Tournament.Gender.MIXED

    def test_str_returns_name(self) -> None:
        tournament = TournamentFactory(name="Grand Slam Paris")
        assert str(tournament) == "Grand Slam Paris"

    def test_created_at_and_updated_at_are_set_automatically(self) -> None:
        tournament = TournamentFactory()
        assert tournament.created_at is not None
        assert tournament.updated_at is not None

    def test_category_choices_are_valid(self) -> None:
        valid_categories = [c.value for c in Tournament.Category]
        assert "P25" in valid_categories
        assert "P50" in valid_categories
        assert "P100" in valid_categories
        assert "P250" in valid_categories
        assert "P500" in valid_categories
        assert "P1000" in valid_categories
        assert "P2000" in valid_categories
        assert len(valid_categories) == 7

    def test_league_choices_are_valid(self) -> None:
        valid_leagues = [league.value for league in Tournament.League]
        assert "Auvergne-Rhône-Alpes" in valid_leagues
        assert "Ile de France" in valid_leagues
        assert "Provence-Alpes-Côtes d'Azur" in valid_leagues
        assert len(valid_leagues) == 18

    def test_gender_choices_are_valid(self) -> None:
        valid_genders = [g.value for g in Tournament.Gender]
        assert "Homme" in valid_genders
        assert "Femme" in valid_genders
        assert "Mixte" in valid_genders
        assert len(valid_genders) == 3


@pytest.mark.django_db
class TestGameFormatDefaultDurations:
    def test_game_format_default_durations_covers_all_formats(self) -> None:
        for fmt in Tournament.GameFormat:
            assert fmt in Tournament.GAME_FORMAT_DEFAULT_DURATIONS

    def test_game_format_default_durations_values(self) -> None:
        expected = {
            "A1": 100,
            "A2": 90,
            "B1": 70,
            "B2": 60,
            "C1": 50,
            "C2": 45,
            "D1": 50,
            "D2": 45,
            "E": 20,
            "F": 25,
        }
        assert Tournament.GAME_FORMAT_DEFAULT_DURATIONS == expected
