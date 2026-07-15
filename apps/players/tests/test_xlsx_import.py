"""Tests for the Excel (.xlsx) pair import endpoint.

Replaces the old .xls (xlrd) import: the JAP now provides a modern .xlsx
export with a sheet named "Tableau final", one row per pair (columns
suffixed " joueur 1"/" joueur 2"), plus a "Poids paire" column.
"""

import datetime
import io
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pytest
from rest_framework.test import APIClient

from apps.notifications.services import Resource
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IMPORT_URL = "/api/v1/tournaments/{tournament_id}/pairs/import/"

SHEET_NAME = "Tableau final"

HEADERS = [
    "Nom de l'épreuve",
    "Catégorie de l'épreuve",
    "Position de la paire",
    "Nom joueur 1",
    "Prénom joueur 1",
    "Date de naissance joueur 1",
    "Licence joueur 1",
    "Club joueur 1",
    "Classement joueur 1",
    "Mail joueur 1",
    "Téléphone joueur 1",
    "Nom joueur 2",
    "Prénom joueur 2",
    "Date de naissance joueur 2",
    "Licence joueur 2",
    "Club joueur 2",
    "Classement joueur 2",
    "Mail joueur 2",
    "Téléphone joueur 2",
    "Poids paire",
]

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def import_url(tournament_id: int) -> str:
    return IMPORT_URL.format(tournament_id=tournament_id)


def _default_row() -> dict:
    return {
        "Nom de l'épreuve": "Messieurs P100",
        "Catégorie de l'épreuve": "Senior",
        "Position de la paire": "",
        "Nom joueur 1": "Martin",
        "Prénom joueur 1": "Julien",
        "Date de naissance joueur 1": datetime.date(1994, 4, 2),
        "Licence joueur 1": "LIC0000001",
        "Club joueur 1": "TC Paris",
        "Classement joueur 1": "250",
        "Mail joueur 1": "julien.martin@example.com",
        "Téléphone joueur 1": "0612345678",
        "Nom joueur 2": "Roux",
        "Prénom joueur 2": "Quentin",
        "Date de naissance joueur 2": datetime.date(1990, 1, 15),
        "Licence joueur 2": "LIC0000002",
        "Club joueur 2": "TC Lyon",
        "Classement joueur 2": "310",
        "Mail joueur 2": "quentin.roux@example.com",
        "Téléphone joueur 2": "0677889900",
        "Poids paire": "560.0",
    }


def make_xlsx_content(
    *rows: dict,
    headers: list[str] | None = None,
    sheet_name: str = SHEET_NAME,
    extra_sheets: list[str] | None = None,
) -> bytes:
    """Build an in-memory .xlsx workbook (openpyxl) with a sheet of the given name.

    Each row dict is merged on top of `_default_row()` so tests only need to
    override the columns they actually care about. Pass headers=None to use
    the real header row; pass an explicit `headers` list to simulate broken
    files. Date values (datetime.date) are written as-is: openpyxl stores
    them natively as dates, no special cell style is needed (unlike xlwt).
    """
    workbook = openpyxl.Workbook()
    default_sheet = workbook.active
    for extra in extra_sheets or []:
        workbook.create_sheet(extra)
    sheet = workbook.create_sheet(sheet_name)
    workbook.remove(default_sheet)

    header_row = headers if headers is not None else HEADERS
    for col, header in enumerate(header_row, start=1):
        sheet.cell(row=1, column=col, value=header)

    for row_idx, overrides in enumerate(rows, start=2):
        row = {**_default_row(), **overrides}
        for col, header in enumerate(header_row, start=1):
            value = row.get(header, "")
            sheet.cell(row=row_idx, column=col, value=value)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def make_xlsx_number_content_with_numeric_license(
    license_j1: str, license_j2: str
) -> bytes:
    """Build a workbook where Licence joueur 1 is written as a plain Excel
    number (e.g. 1234567), to verify no '.0' artifact leaks into the stored
    value.
    """
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = SHEET_NAME
    for col, header in enumerate(HEADERS, start=1):
        sheet.cell(row=1, column=col, value=header)

    row = {
        **_default_row(),
        "Licence joueur 1": license_j1,
        "Licence joueur 2": license_j2,
    }
    for col, header in enumerate(HEADERS, start=1):
        value = row.get(header, "")
        if header == "Licence joueur 1":
            sheet.cell(row=2, column=col, value=float(value))
        else:
            sheet.cell(row=2, column=col, value=value)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def make_xlsx_file(content: bytes, filename: str = "participants.xlsx") -> io.BytesIO:
    f = io.BytesIO(content)
    f.name = filename
    return f


def make_xlsx_number_content(*rows: dict) -> bytes:
    """Build a workbook where Licence/Classement/Poids paire are written as
    Excel *numbers* instead of text, to test robustness.
    """
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = SHEET_NAME
    for col, header in enumerate(HEADERS, start=1):
        sheet.cell(row=1, column=col, value=header)

    numeric_headers = {"Classement joueur 1", "Classement joueur 2", "Poids paire"}

    for row_idx, overrides in enumerate(rows, start=2):
        row = {**_default_row(), **overrides}
        for col, header in enumerate(HEADERS, start=1):
            value = row.get(header, "")
            if header in numeric_headers and value != "":
                sheet.cell(row=row_idx, column=col, value=float(value))
            else:
                sheet.cell(row=row_idx, column=col, value=value)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def other_user():
    return UserFactory()


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def tournament(user):
    return TournamentFactory(owner=user)


@pytest.fixture
def other_tournament(other_user):
    return TournamentFactory(owner=other_user)


# ---------------------------------------------------------------------------
# TestXlsxImportHappyPath
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsxImportHappyPath:
    def test_xlsx_import_requires_auth(self, tournament):
        client = APIClient()
        content = make_xlsx_content()
        f = make_xlsx_file(content)
        response = client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 401

    def test_xlsx_import_success_creates_pair(self, auth_client, tournament):
        content = make_xlsx_content(
            {"Licence joueur 1": "XLSX0000001", "Licence joueur 2": "XLSX0000002"}
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert len(response.data) == 1

    def test_xlsx_import_notifies_pairs_and_tournament(self, auth_client, tournament):
        content = make_xlsx_content(
            {"Licence joueur 1": "NOTIFXLSX001", "Licence joueur 2": "NOTIFXLSX002"}
        )
        f = make_xlsx_file(content)

        with patch("apps.players.views.notify_public_update") as mock_notify:
            response = auth_client.post(
                import_url(tournament.id), data={"file": f}, format="multipart"
            )

        assert response.status_code == 201
        mock_notify.assert_called_once_with(
            tournament, Resource.PAIRS, Resource.TOURNAMENT
        )

    def test_xlsx_import_creates_players_with_all_fields(self, auth_client, tournament):
        from apps.players.models import Player

        content = make_xlsx_content(
            {"Licence joueur 1": "FULL0000001", "Licence joueur 2": "FULL0000002"}
        )
        f = make_xlsx_file(content)
        auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )

        p1 = Player.objects.get(license_number="FULL0000001")
        p2 = Player.objects.get(license_number="FULL0000002")

        assert p1.last_name == "Martin"
        assert p1.first_name == "Julien"
        assert p1.birth_date == datetime.date(1994, 4, 2)
        assert p1.club == "TC Paris"
        assert p1.email == "julien.martin@example.com"
        assert p1.phone == "0612345678"
        assert p1.ranking == 250

        assert p2.last_name == "Roux"
        assert p2.first_name == "Quentin"
        assert p2.birth_date == datetime.date(1990, 1, 15)
        assert p2.club == "TC Lyon"
        assert p2.email == "quentin.roux@example.com"
        assert p2.phone == "0677889900"
        assert p2.ranking == 310

    def test_xlsx_import_sets_pair_weight(self, auth_client, tournament):
        from apps.players.models import Pair

        content = make_xlsx_content(
            {
                "Licence joueur 1": "WEIGHT0001",
                "Licence joueur 2": "WEIGHT0002",
                "Poids paire": "560.0",
            }
        )
        f = make_xlsx_file(content)
        auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        pair = Pair.objects.get(
            tournament=tournament,
            player1__license_number="WEIGHT0001",
            player2__license_number="WEIGHT0002",
        )
        assert pair.weight == 560.0

    def test_xlsx_import_birth_date_text_fallback(self, auth_client, tournament):
        """Date de naissance joueur 1/2 may come back as plain text JJ/MM/AAAA
        instead of a native date cell."""
        from apps.players.models import Player

        content = make_xlsx_content(
            {
                "Licence joueur 1": "TEXTDATE001",
                "Licence joueur 2": "TEXTDATE002",
                "Date de naissance joueur 1": "02/04/1994",
                "Date de naissance joueur 2": "15/01/1990",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        p1 = Player.objects.get(license_number="TEXTDATE001")
        p2 = Player.objects.get(license_number="TEXTDATE002")
        assert p1.birth_date == datetime.date(1994, 4, 2)
        assert p2.birth_date == datetime.date(1990, 1, 15)

    def test_xlsx_import_ignores_epreuve_categorie_rang(self, auth_client, tournament):
        """Nom de l'épreuve / Catégorie de l'épreuve / Position de la paire are
        read but never stored anywhere."""
        content = make_xlsx_content(
            {
                "Licence joueur 1": "IGNORE0001",
                "Licence joueur 2": "IGNORE0002",
                "Nom de l'épreuve": "Some Event",
                "Catégorie de l'épreuve": "Senior +35",
                "Position de la paire": "12",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        # Sanity: nothing on Player/Pair references these values; if creation
        # succeeds with the normal expected fields, they were simply ignored.
        from apps.players.models import Player

        assert Player.objects.filter(license_number="IGNORE0001").exists()

    def test_xlsx_import_response_contains_all_tournament_pairs(
        self, auth_client, tournament
    ):
        from apps.players.tests.factories import PairFactory

        PairFactory(tournament=tournament)
        content = make_xlsx_content(
            {"Licence joueur 1": "ALLPAIRS001", "Licence joueur 2": "ALLPAIRS002"}
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert len(response.data) == 2


# ---------------------------------------------------------------------------
# TestXlsxImportLicenseSeasonSuffix
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsxImportLicenseSeasonSuffix:
    def test_license_season_suffix_is_stripped(self, auth_client, tournament):
        from apps.players.models import Player

        content = make_xlsx_content(
            {
                "Licence joueur 1": "3271896H (2026)",
                "Licence joueur 2": "LICNOSUFFIX002",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert Player.objects.filter(license_number="3271896H").exists()
        assert not Player.objects.filter(license_number="3271896H (2026)").exists()

    def test_license_without_suffix_is_unchanged(self, auth_client, tournament):
        from apps.players.models import Player

        content = make_xlsx_content(
            {
                "Licence joueur 1": "LICNOSUFFIX001",
                "Licence joueur 2": "LICNOSUFFIX002",
            }
        )
        f = make_xlsx_file(content)
        auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert Player.objects.filter(license_number="LICNOSUFFIX001").exists()

    def test_reimport_next_season_updates_same_player(self, auth_client, tournament):
        """Re-importing the same player next season (different year suffix)
        updates the existing Player rather than creating a duplicate."""
        from apps.players.models import Player

        content_2026 = make_xlsx_content(
            {
                "Licence joueur 1": "3271896H (2026)",
                "Licence joueur 2": "SEASONOTHER002",
                "Nom joueur 1": "Martin",
            }
        )
        f1 = make_xlsx_file(content_2026)
        auth_client.post(
            import_url(tournament.id), data={"file": f1}, format="multipart"
        )
        assert Player.objects.filter(license_number="3271896H").count() == 1

        content_2027 = make_xlsx_content(
            {
                "Licence joueur 1": "3271896H (2027)",
                "Licence joueur 2": "SEASONOTHER002",
                "Nom joueur 1": "MartinUpdated",
            }
        )
        f2 = make_xlsx_file(content_2027)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f2}, format="multipart"
        )
        assert response.status_code == 201
        assert Player.objects.filter(license_number="3271896H").count() == 1
        player = Player.objects.get(license_number="3271896H")
        assert player.last_name == "MartinUpdated"


# ---------------------------------------------------------------------------
# TestXlsxImportCellTypeRobustness
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsxImportCellTypeRobustness:
    def test_classement_weight_as_excel_numbers_no_dot_zero_artifact(
        self, auth_client, tournament
    ):
        """Classement/Poids paire written as Excel numbers (not text) must
        still parse without a trailing '.0' artifact on integer fields."""
        from apps.players.models import Pair, Player

        content = make_xlsx_number_content(
            {
                "Licence joueur 1": "NUM0000001",
                "Licence joueur 2": "NUM0000002",
                "Classement joueur 1": "250",
                "Classement joueur 2": "310",
                "Poids paire": "560.0",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201

        p1 = Player.objects.get(license_number="NUM0000001")
        p2 = Player.objects.get(license_number="NUM0000002")
        assert p1.ranking == 250
        assert p2.ranking == 310

        pair = Pair.objects.get(
            tournament=tournament,
            player1__license_number="NUM0000001",
            player2__license_number="NUM0000002",
        )
        assert pair.weight == 560.0

    def test_licence_as_excel_number_no_dot_zero_artifact(
        self, auth_client, tournament
    ):
        """A license number written as an Excel number must not become '1234567.0'."""
        from apps.players.models import Player

        workbook_bytes = make_xlsx_number_content_with_numeric_license(
            license_j1="1234567", license_j2="NUMLICOTHER002"
        )
        f = make_xlsx_file(workbook_bytes)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert Player.objects.filter(license_number="1234567").exists()
        assert not Player.objects.filter(license_number="1234567.0").exists()

    def test_poids_paire_as_non_integer_excel_number(self, auth_client, tournament):
        """A non-integer Excel number (e.g. 560.5) must round-trip exactly,
        not get truncated by the integer-stripping logic reserved for
        integer-looking numeric cells."""
        from apps.players.models import Pair

        content = make_xlsx_number_content(
            {
                "Licence joueur 1": "NUMFLOAT001",
                "Licence joueur 2": "NUMFLOAT002",
                "Poids paire": "560.5",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        pair = Pair.objects.get(
            tournament=tournament,
            player1__license_number="NUMFLOAT001",
            player2__license_number="NUMFLOAT002",
        )
        assert pair.weight == 560.5


# ---------------------------------------------------------------------------
# TestXlsxImportPriorityRules
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsxImportPriorityRules:
    def test_ranking_from_file_overrides_existing_db_value(
        self, auth_client, tournament
    ):
        from apps.players.models import Player

        Player.objects.create(
            last_name="Martin",
            first_name="Julien",
            license_number="PRIO0000001",
            ranking=100,
        )
        content = make_xlsx_content(
            {
                "Licence joueur 1": "PRIO0000001",
                "Licence joueur 2": "PRIO0000002",
                "Classement joueur 1": "999",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        player = Player.objects.get(license_number="PRIO0000001")
        assert player.ranking == 999

    def test_empty_ranking_cell_preserves_existing_db_value(
        self, auth_client, tournament
    ):
        from apps.players.models import Player

        Player.objects.create(
            last_name="Martin",
            first_name="Julien",
            license_number="PRIO0000003",
            ranking=150,
        )
        content = make_xlsx_content(
            {
                "Licence joueur 1": "PRIO0000003",
                "Licence joueur 2": "PRIO0000004",
                "Classement joueur 1": "",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        player = Player.objects.get(license_number="PRIO0000003")
        assert player.ranking == 150

    def test_new_player_with_empty_ranking_cell_has_ranking_none(
        self, auth_client, tournament
    ):
        from apps.players.models import Player

        content = make_xlsx_content(
            {
                "Licence joueur 1": "PRIO0000005",
                "Licence joueur 2": "PRIO0000006",
                "Classement joueur 1": "",
                "Classement joueur 2": "",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        p1 = Player.objects.get(license_number="PRIO0000005")
        assert p1.ranking is None

    def test_weight_from_file_overrides_existing_pair_weight(
        self, auth_client, tournament
    ):
        from apps.players.tests.factories import PairFactory, PlayerFactory

        player1 = PlayerFactory(license_number="WPRIO0000001")
        player2 = PlayerFactory(license_number="WPRIO0000002")
        existing_pair = PairFactory(
            tournament=tournament, player1=player1, player2=player2, weight=100.0
        )

        content = make_xlsx_content(
            {
                "Licence joueur 1": "WPRIO0000001",
                "Licence joueur 2": "WPRIO0000002",
                "Poids paire": "999.0",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        existing_pair.refresh_from_db()
        assert existing_pair.weight == 999.0

    def test_empty_weight_cell_preserves_existing_pair_weight(
        self, auth_client, tournament
    ):
        from apps.players.tests.factories import PairFactory, PlayerFactory

        player1 = PlayerFactory(license_number="WPRIO0000003")
        player2 = PlayerFactory(license_number="WPRIO0000004")
        existing_pair = PairFactory(
            tournament=tournament, player1=player1, player2=player2, weight=150.0
        )

        content = make_xlsx_content(
            {
                "Licence joueur 1": "WPRIO0000003",
                "Licence joueur 2": "WPRIO0000004",
                "Poids paire": "",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        existing_pair.refresh_from_db()
        assert existing_pair.weight == 150.0

    def test_birth_date_from_file_overrides_existing_value(
        self, auth_client, tournament
    ):
        from apps.players.models import Player

        Player.objects.create(
            last_name="Martin",
            first_name="Julien",
            license_number="BPRIO0000001",
            birth_date=datetime.date(1980, 1, 1),
        )
        content = make_xlsx_content(
            {
                "Licence joueur 1": "BPRIO0000001",
                "Licence joueur 2": "BPRIO0000002",
                "Date de naissance joueur 1": datetime.date(1999, 12, 31),
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        player = Player.objects.get(license_number="BPRIO0000001")
        assert player.birth_date == datetime.date(1999, 12, 31)

    def test_empty_birth_date_cell_preserves_existing_value(
        self, auth_client, tournament
    ):
        from apps.players.models import Player

        Player.objects.create(
            last_name="Martin",
            first_name="Julien",
            license_number="BPRIO0000003",
            birth_date=datetime.date(1980, 1, 1),
        )
        content = make_xlsx_content(
            {
                "Licence joueur 1": "BPRIO0000003",
                "Licence joueur 2": "BPRIO0000004",
                "Date de naissance joueur 1": "",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        player = Player.objects.get(license_number="BPRIO0000003")
        assert player.birth_date == datetime.date(1980, 1, 1)


# ---------------------------------------------------------------------------
# TestXlsxImportValidationErrors
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsxImportValidationErrors:
    def test_no_file(self, auth_client, tournament):
        response = auth_client.post(
            import_url(tournament.id), data={}, format="multipart"
        )
        assert response.status_code == 400

    def test_wrong_extension(self, auth_client, tournament):
        f = io.BytesIO(b"not an xlsx file")
        f.name = "pairs.csv"
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_corrupt_unreadable_file(self, auth_client, tournament):
        f = io.BytesIO(b"this is not a valid xlsx binary content at all !!!")
        f.name = "participants.xlsx"
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_missing_tableau_final_sheet_only_joueurs_sheet(
        self, auth_client, tournament
    ):
        workbook = openpyxl.Workbook()
        workbook.active.title = "Joueurs"
        buffer = io.BytesIO()
        workbook.save(buffer)
        f = make_xlsx_file(buffer.getvalue())
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_missing_tableau_final_sheet_unrelated_sheet_name(
        self, auth_client, tournament
    ):
        workbook = openpyxl.Workbook()
        workbook.active.title = "Feuille1"
        buffer = io.BytesIO()
        workbook.save(buffer)
        f = make_xlsx_file(buffer.getvalue())
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_missing_header_row(self, auth_client, tournament):
        workbook = openpyxl.Workbook()
        workbook.active.title = SHEET_NAME
        buffer = io.BytesIO()
        workbook.save(buffer)
        f = make_xlsx_file(buffer.getvalue())
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_invalid_header_row_missing_column(self, auth_client, tournament):
        broken_headers = [h for h in HEADERS if h != "Licence joueur 1"]
        content = make_xlsx_content(
            {"Licence joueur 2": "BADHEADER002"}, headers=broken_headers
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_missing_license_j1(self, auth_client, tournament):
        content = make_xlsx_content(
            {"Licence joueur 1": "", "Licence joueur 2": "MISSLIC002"}
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_missing_license_j2(self, auth_client, tournament):
        content = make_xlsx_content(
            {"Licence joueur 1": "MISSLIC001", "Licence joueur 2": ""}
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_duplicate_license_within_file(self, auth_client, tournament):
        content = make_xlsx_content(
            {"Licence joueur 1": "DUPLIC001", "Licence joueur 2": "DUPLIC002"},
            {"Licence joueur 1": "DUPLIC001", "Licence joueur 2": "DUPLIC003"},
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_invalid_birth_date_text(self, auth_client, tournament):
        content = make_xlsx_content(
            {
                "Licence joueur 1": "BADDATE001",
                "Licence joueur 2": "BADDATE002",
                "Date de naissance joueur 1": "not-a-date",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_invalid_birth_date_text_for_player2(self, auth_client, tournament):
        """Same validation must apply to joueur 2's birth date, not just joueur 1's."""
        content = make_xlsx_content(
            {
                "Licence joueur 1": "BADDATE003",
                "Licence joueur 2": "BADDATE004",
                "Date de naissance joueur 2": "not-a-date",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_header_only_file_succeeds_no_pairs_created(self, auth_client, tournament):
        from apps.players.models import Pair

        content = make_xlsx_content()  # no rows passed
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert Pair.objects.filter(tournament=tournament).count() == 0

    def test_blank_row_is_silently_ignored(self, auth_client, tournament):
        """A fully blank row (residual formatting row at the end of a real
        export) must be skipped rather than raising a validation error."""
        from apps.players.models import Pair

        content = make_xlsx_content(
            {"Licence joueur 1": "BLANKROW001", "Licence joueur 2": "BLANKROW002"}
        )
        # _default_row() always fills every column, so a genuinely blank row
        # (all cells None) has to be appended by writing directly into the
        # workbook after the fact, past the one real data row.
        workbook = openpyxl.load_workbook(io.BytesIO(content))
        sheet = workbook[SHEET_NAME]
        blank_row_idx = sheet.max_row + 1
        for col in range(1, len(HEADERS) + 1):
            sheet.cell(row=blank_row_idx, column=col, value=None)
        buffer = io.BytesIO()
        workbook.save(buffer)

        f = make_xlsx_file(buffer.getvalue())
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert Pair.objects.filter(tournament=tournament).count() == 1
        assert (
            Pair.objects.filter(
                tournament=tournament,
                player1__license_number="BLANKROW001",
                player2__license_number="BLANKROW002",
            ).count()
            == 1
        )

    def test_locked_tournament_started_returns_409(self, auth_client, tournament):
        from apps.players.models import Pair

        tournament.status = Tournament.Status.STARTED
        tournament.save()
        content = make_xlsx_content(
            {"Licence joueur 1": "LOCKED0001", "Licence joueur 2": "LOCKED0002"}
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 409
        assert not Pair.objects.filter(tournament=tournament).exists()

    def test_locked_tournament_finished_returns_409(self, auth_client, tournament):
        from apps.players.models import Pair

        tournament.status = Tournament.Status.FINISHED
        tournament.save()
        content = make_xlsx_content(
            {"Licence joueur 1": "LOCKED0003", "Licence joueur 2": "LOCKED0004"}
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 409
        assert not Pair.objects.filter(tournament=tournament).exists()

    def test_wrong_owner_tournament_returns_404(self, auth_client, other_tournament):
        content = make_xlsx_content()
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(other_tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, tournament):
        client = APIClient()
        content = make_xlsx_content()
        f = make_xlsx_file(content)
        response = client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# TestXlsxImportAutoFFTMatching
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsxImportAutoFFTMatching:
    """After an xlsx import, FFT ranking matching is automatically triggered
    as a safety net for players whose 'Classement' cell was empty in the file.
    """

    def _make_tournament(self, user, gender=None, league=None):
        return TournamentFactory(
            owner=user,
            gender=gender or Tournament.Gender.MALE,
            league=league or Tournament.League.ILE_DE_FRANCE,
        )

    def test_empty_ranking_cell_filled_by_fft_match(self, auth_client, user):
        from apps.players.models import Player
        from apps.players.tests.factories import FFTRankingFactory

        tournament = self._make_tournament(user)

        FFTRankingFactory(
            last_name="Dupont",
            first_name="Alice",
            ranking=120,
            gender=Tournament.Gender.MALE,
            league=Tournament.League.ILE_DE_FRANCE,
        )
        FFTRankingFactory(
            last_name="Bernard",
            first_name="Bob",
            ranking=180,
            gender=Tournament.Gender.MALE,
            league=Tournament.League.ILE_DE_FRANCE,
        )

        content = make_xlsx_content(
            {
                "Nom joueur 1": "Dupont",
                "Prénom joueur 1": "Alice",
                "Licence joueur 1": "AUTOFFT0001",
                "Classement joueur 1": "",
                "Nom joueur 2": "Bernard",
                "Prénom joueur 2": "Bob",
                "Licence joueur 2": "AUTOFFT0002",
                "Classement joueur 2": "",
                "Poids paire": "",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )

        assert response.status_code == 201
        p1 = Player.objects.get(license_number="AUTOFFT0001")
        p2 = Player.objects.get(license_number="AUTOFFT0002")
        assert p1.ranking == 120
        assert p2.ranking == 180
        assert response.data[0]["weight"] == 300.0

    def test_fft_matching_does_not_overwrite_ranking_from_file(self, auth_client, user):
        """If the file provided a Classement value, FFT matching must not touch it."""
        from apps.players.models import Player
        from apps.players.tests.factories import FFTRankingFactory

        tournament = self._make_tournament(user)

        FFTRankingFactory(
            last_name="Leroy",
            first_name="Paul",
            ranking=999,
            gender=Tournament.Gender.MALE,
        )
        FFTRankingFactory(
            last_name="Simon",
            first_name="Jean",
            ranking=888,
            gender=Tournament.Gender.MALE,
        )

        content = make_xlsx_content(
            {
                "Nom joueur 1": "Leroy",
                "Prénom joueur 1": "Paul",
                "Licence joueur 1": "NOOVERWRITE0001",
                "Classement joueur 1": "50",
                "Nom joueur 2": "Simon",
                "Prénom joueur 2": "Jean",
                "Licence joueur 2": "NOOVERWRITE0002",
                "Classement joueur 2": "75",
            }
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )

        assert response.status_code == 201
        p1 = Player.objects.get(license_number="NOOVERWRITE0001")
        p2 = Player.objects.get(license_number="NOOVERWRITE0002")
        assert p1.ranking == 50
        assert p2.ranking == 75


# ---------------------------------------------------------------------------
# TestXlsxImportNonRegression
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsxImportNonRegression:
    def test_existing_pairs_not_in_file_are_preserved(self, auth_client, tournament):
        from apps.players.models import Pair
        from apps.players.tests.factories import PairFactory

        existing_pair = PairFactory(tournament=tournament)
        existing_pair_id = existing_pair.id

        content = make_xlsx_content(
            {"Licence joueur 1": "NONREG0001", "Licence joueur 2": "NONREG0002"}
        )
        f = make_xlsx_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert Pair.objects.filter(id=existing_pair_id).exists()
        assert Pair.objects.filter(tournament=tournament).count() == 2

    def test_reimport_same_players_updates_instead_of_duplicating_pair(
        self, auth_client, tournament
    ):
        from apps.players.models import Pair

        content = make_xlsx_content(
            {
                "Licence joueur 1": "REIMPORT0001",
                "Licence joueur 2": "REIMPORT0002",
                "Poids paire": "300.0",
            }
        )
        f1 = make_xlsx_file(content)
        auth_client.post(
            import_url(tournament.id), data={"file": f1}, format="multipart"
        )
        assert Pair.objects.filter(tournament=tournament).count() == 1

        content2 = make_xlsx_content(
            {
                "Licence joueur 1": "REIMPORT0001",
                "Licence joueur 2": "REIMPORT0002",
                "Poids paire": "450.0",
                "Club joueur 1": "Nouveau Club",
            }
        )
        f2 = make_xlsx_file(content2)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f2}, format="multipart"
        )
        assert response.status_code == 201
        assert Pair.objects.filter(tournament=tournament).count() == 1

        pair = Pair.objects.get(
            tournament=tournament,
            player1__license_number="REIMPORT0001",
            player2__license_number="REIMPORT0002",
        )
        assert pair.weight == 450.0
        assert pair.player1.club == "Nouveau Club"

    def test_real_export_file_imports_successfully(self, auth_client, tournament):
        """Import the real .xlsx export file provided by the user (8 pairs).

        Exercises, in a single pass, the exact shape of a real production
        file: birth dates stored as JJ/MM/AAAA text, Classement/Poids paire
        stored as native Excel numbers (float), and license numbers stored
        as text — a natural regression check on real-world data.
        """
        from apps.players.models import Pair, Player

        fixture_path = FIXTURES_DIR / "liste_participants_padel.xlsx"
        with open(fixture_path, "rb") as fh:
            f = io.BytesIO(fh.read())
        f.name = "liste_participants_padel.xlsx"

        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )

        assert response.status_code == 201
        assert len(response.data) == 8

        player1 = Player.objects.get(license_number="9230781")
        assert player1.last_name == "CASANOVAS"
        assert player1.first_name == "Christophe"
        assert player1.birth_date == datetime.date(1988, 2, 10)
        assert player1.club == "TENNIS CLUB DU VALLESPIR MAUREILLAS"
        assert player1.ranking == 10000
        assert player1.email == "christophecasanovas@hotmail.com"
        assert player1.phone == "0621542262"

        pair = Pair.objects.get(
            tournament=tournament,
            player1__license_number="9230781",
            player2__license_number="3257655",
        )
        assert pair.weight == 22859.0
