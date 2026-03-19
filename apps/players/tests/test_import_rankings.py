"""Tests for the import_fft_rankings management command.

Parser correctness is tested separately in test_pdf_parser.py.  Here we
focus on the *import behaviour*: database records, meta updates, idempotency,
gender isolation, and error handling.

parse_fft_pdf is mocked so tests are fast and independent of PDF content.
"""
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.players.models import FFTRanking, FFTRankingMeta
from apps.players.services.pdf_parser_service import ParsedRankingEntry
from apps.tournaments.models import Tournament

_PARSE_PATH = "apps.players.management.commands.import_fft_rankings.parse_fft_pdf"

MOCK_MEN = [
    ParsedRankingEntry("LEYGUE", "Thomas", 1, None, "Ile de France"),
    ParsedRankingEntry("HOUSSAIN", "Robin", 226, 6140.0, "Occitanie"),
    ParsedRankingEntry("NIOT", "Clément", 13296, 495.0, "Occitanie"),
    ParsedRankingEntry("CABANES", "Eric", 16085, 365.0, "Occitanie"),
]

MOCK_WOMEN = [
    ParsedRankingEntry("DUPONT", "Marie", 1, None, "Ile de France"),
    ParsedRankingEntry("MARTIN", "Sophie", 2, 5000.0, "Occitanie"),
]


@pytest.mark.django_db
class TestImportMen:
    def test_import_men_creates_records(self, men_pdf_path: str) -> None:
        with patch(_PARSE_PATH, return_value=MOCK_MEN):
            call_command("import_fft_rankings", men=men_pdf_path)
        assert FFTRanking.objects.filter(gender=Tournament.Gender.MALE).count() == 4

    def test_import_meta_created(self, men_pdf_path: str) -> None:
        with patch(_PARSE_PATH, return_value=MOCK_MEN):
            call_command("import_fft_rankings", men=men_pdf_path)
        meta = FFTRankingMeta.objects.get(gender=Tournament.Gender.MALE)
        assert meta.entry_count == 4
        assert meta.last_imported_at is not None
        assert meta.source_filename != ""


@pytest.mark.django_db
class TestImportWomen:
    def test_import_women_creates_records(self, women_pdf_path: str) -> None:
        with patch(_PARSE_PATH, return_value=MOCK_WOMEN):
            call_command("import_fft_rankings", women=women_pdf_path)
        assert FFTRanking.objects.filter(gender=Tournament.Gender.FEMALE).count() == 2

    def test_import_women_meta_created(self, women_pdf_path: str) -> None:
        with patch(_PARSE_PATH, return_value=MOCK_WOMEN):
            call_command("import_fft_rankings", women=women_pdf_path)
        meta = FFTRankingMeta.objects.get(gender=Tournament.Gender.FEMALE)
        assert meta.entry_count == 2


@pytest.mark.django_db
class TestImportBoth:
    def test_import_both(self, men_pdf_path: str, women_pdf_path: str) -> None:
        with patch(_PARSE_PATH, side_effect=[MOCK_MEN, MOCK_WOMEN]):
            call_command("import_fft_rankings", men=men_pdf_path, women=women_pdf_path)
        assert FFTRanking.objects.filter(gender=Tournament.Gender.MALE).count() == 4
        assert FFTRanking.objects.filter(gender=Tournament.Gender.FEMALE).count() == 2


@pytest.mark.django_db
class TestNoDuplicateOnReimport:
    def test_no_duplicate_on_reimport(self, men_pdf_path: str) -> None:
        with patch(_PARSE_PATH, return_value=MOCK_MEN):
            call_command("import_fft_rankings", men=men_pdf_path)
        with patch(_PARSE_PATH, return_value=MOCK_MEN):
            call_command("import_fft_rankings", men=men_pdf_path)
        assert FFTRanking.objects.filter(gender=Tournament.Gender.MALE).count() == 4

    def test_men_import_does_not_affect_women(
        self, men_pdf_path: str, women_pdf_path: str
    ) -> None:
        with patch(_PARSE_PATH, return_value=MOCK_WOMEN):
            call_command("import_fft_rankings", women=women_pdf_path)
        women_before = FFTRanking.objects.filter(gender=Tournament.Gender.FEMALE).count()

        with patch(_PARSE_PATH, return_value=MOCK_MEN):
            call_command("import_fft_rankings", men=men_pdf_path)

        women_after = FFTRanking.objects.filter(gender=Tournament.Gender.FEMALE).count()
        assert women_before == women_after == 2


@pytest.mark.django_db
class TestCommandErrors:
    def test_no_args_raises_command_error(self) -> None:
        with pytest.raises(CommandError):
            call_command("import_fft_rankings")

    def test_missing_file_raises_system_exit(self) -> None:
        with pytest.raises(SystemExit):
            call_command("import_fft_rankings", men="/nonexistent/path/ranking.pdf")


@pytest.mark.django_db
class TestMetaUpdatedOnReimport:
    def test_meta_updated_on_reimport(self, men_pdf_path: str) -> None:
        with patch(_PARSE_PATH, return_value=MOCK_MEN):
            call_command("import_fft_rankings", men=men_pdf_path)
        with patch(_PARSE_PATH, return_value=MOCK_MEN):
            call_command("import_fft_rankings", men=men_pdf_path)
        meta = FFTRankingMeta.objects.get(gender=Tournament.Gender.MALE)
        assert meta.entry_count == 4
        assert meta.last_imported_at is not None
