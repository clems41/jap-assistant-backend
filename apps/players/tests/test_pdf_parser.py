"""Tests for the FFT ranking PDF parser service.

These tests use the *real* FFT ranking PDFs mounted at input_pdf/.
Known ground-truth players (from the plan examples) are checked by name so
that test failures are meaningful even if surrounding ranking positions shift.
"""
import pytest

from apps.players.services.pdf_parser_service import (
    ParsedRankingEntry,
    PDFFormatUnknownError,
    PDFParseError,
    parse_fft_pdf,
)


# ---------------------------------------------------------------------------
# Shared fixture: parse the men's PDF once per test session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def men_entries(men_pdf_path: str) -> list[ParsedRankingEntry]:
    """Parse the real FFT men's PDF once and reuse the result across tests."""
    return parse_fft_pdf(men_pdf_path)


@pytest.fixture(scope="module")
def women_entries(women_pdf_path: str) -> list[ParsedRankingEntry]:
    """Parse the real FFT women's PDF once and reuse the result across tests."""
    return parse_fft_pdf(women_pdf_path)


# ---------------------------------------------------------------------------
# Men's PDF — known ground-truth players
# ---------------------------------------------------------------------------


class TestKnownPlayers:
    def test_leygue_thomas_rank_1(self, men_entries: list[ParsedRankingEntry]) -> None:
        leygue = next(
            (e for e in men_entries if e.last_name == "LEYGUE" and e.first_name == "Thomas"),
            None,
        )
        assert leygue is not None, "LEYGUE Thomas not found in parsed entries"
        assert leygue.ranking == 1
        assert leygue.points is None
        assert leygue.league == "Ile de France"

    def test_niot_clement_rank_13296(self, men_entries: list[ParsedRankingEntry]) -> None:
        niot = next((e for e in men_entries if e.last_name == "NIOT"), None)
        assert niot is not None, "NIOT not found in parsed entries"
        assert niot.ranking == 13296
        assert niot.points == 495.0
        assert niot.league == "Occitanie"

    def test_houssain_robin_rank_226(self, men_entries: list[ParsedRankingEntry]) -> None:
        houssain = next((e for e in men_entries if e.last_name == "HOUSSAIN"), None)
        assert houssain is not None, "HOUSSAIN not found in parsed entries"
        assert houssain.ranking == 226
        assert houssain.points == 6140.0
        assert houssain.league == "Occitanie"

    def test_cabanes_eric_rank_16085(self, men_entries: list[ParsedRankingEntry]) -> None:
        cabanes = next(
            (e for e in men_entries if e.last_name == "CABANES" and e.first_name == "Eric"),
            None,
        )
        assert cabanes is not None, "CABANES Eric not found in parsed entries"
        assert cabanes.ranking == 16085
        assert cabanes.points == 365.0
        assert cabanes.league == "Occitanie"


class TestThousandSeparators:
    def test_rank_nbsp_separator(self, men_entries: list[ParsedRankingEntry]) -> None:
        """Rank "13\xa0296" in the PDF must be parsed as the integer 13296."""
        niot = next((e for e in men_entries if e.last_name == "NIOT"), None)
        assert niot is not None
        assert niot.ranking == 13296

    def test_rank_nbsp_separator_large(self, men_entries: list[ParsedRankingEntry]) -> None:
        cabanes = next(
            (e for e in men_entries if e.last_name == "CABANES" and e.first_name == "Eric"),
            None,
        )
        assert cabanes is not None
        assert cabanes.ranking == 16085

    def test_points_nbsp_separator(self, men_entries: list[ParsedRankingEntry]) -> None:
        """Points "6\xa0140" in the PDF must be parsed as the float 6140.0."""
        houssain = next((e for e in men_entries if e.last_name == "HOUSSAIN"), None)
        assert houssain is not None
        assert houssain.points == 6140.0


class TestLeagueNormalisation:
    def test_uppercase_occitanie_normalised(self, men_entries: list[ParsedRankingEntry]) -> None:
        """League names in the PDF are ALL-CAPS; they must be normalised to
        the Tournament.League value."""
        houssain = next((e for e in men_entries if e.last_name == "HOUSSAIN"), None)
        assert houssain is not None
        assert houssain.league == "Occitanie"

    def test_ile_de_france_normalised(self, men_entries: list[ParsedRankingEntry]) -> None:
        leygue = next(
            (e for e in men_entries if e.last_name == "LEYGUE" and e.first_name == "Thomas"),
            None,
        )
        assert leygue is not None
        assert leygue.league == "Ile de France"


class TestWomenKnownPlayers:
    def test_henriot_margot(self, women_entries: list[ParsedRankingEntry]) -> None:
        """Row format: «rank ± NOM Prénom Points Meilleur_class.\\r\\nPays nb_t Ligue»
        Points (74) is the first trailing number; Meilleur class. (7308) must be
        discarded and must NOT pollute first_name."""
        henriot = next(
            (e for e in women_entries if e.last_name == "HENRIOT" and e.first_name == "Margot"),
            None,
        )
        assert henriot is not None, "HENRIOT Margot not found in parsed entries"
        assert henriot.first_name == "Margot"
        assert henriot.points == 74.0
        assert henriot.league == "Occitanie"


class TestParserReturnsManyEntries:
    def test_parse_returns_large_number_of_entries(
        self, men_entries: list[ParsedRankingEntry]
    ) -> None:
        """The real PDF contains thousands of players."""
        assert len(men_entries) > 1000


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestParseFftPdfErrors:
    def test_pdf_format_unknown_error(self, no_header_pdf_path: str) -> None:
        with pytest.raises(PDFFormatUnknownError):
            parse_fft_pdf(no_header_pdf_path)

    def test_pdf_parse_error(self, corrupted_pdf_path: str) -> None:
        with pytest.raises(PDFParseError):
            parse_fft_pdf(corrupted_pdf_path)


# ---------------------------------------------------------------------------
# ParsedRankingEntry dataclass
# ---------------------------------------------------------------------------


class TestParsedRankingEntryDataclass:
    def test_entry_is_dataclass(self) -> None:
        entry = ParsedRankingEntry(
            last_name="TEST",
            first_name="User",
            ranking=42,
            points=100.0,
            league="Occitanie",
        )
        assert entry.last_name == "TEST"
        assert entry.ranking == 42
        assert entry.points == 100.0

    def test_points_nullable(self) -> None:
        entry = ParsedRankingEntry(
            last_name="TEST",
            first_name="User",
            ranking=1,
            points=None,
            league="",
        )
        assert entry.points is None
