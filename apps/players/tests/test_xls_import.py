"""Tests for the Excel (.xls) pair import endpoint.

Replaces the old CSV import (see test_api.py history): the JAP now provides
an Excel 97-2003 (.xls) export with a sheet named "Inscriptions", one row
per pair (columns suffixed " J1"/" J2"), plus a "Poids paire" column.
"""

import datetime
import io

import pytest
import xlwt
from rest_framework.test import APIClient

from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IMPORT_URL = "/api/v1/tournaments/{tournament_id}/pairs/import/"

SHEET_NAME = "Inscriptions"

HEADERS = [
    "Epreuve",
    "Catégorie d'âge",
    "Rang",
    "Nom J1",
    "Prénom J1",
    "Naissance J1",
    "Licence J1",
    "Club J1",
    "Classement J1",
    "Courriel J1",
    "Portable J1",
    "Nom J2",
    "Prénom J2",
    "Naissance J2",
    "Licence J2",
    "Club J2",
    "Classement J2",
    "Courriel J2",
    "Portable J2",
    "Poids paire",
]

DATE_FORMAT = xlwt.XFStyle()
DATE_FORMAT.num_format_str = "DD/MM/YYYY"


def import_url(tournament_id: int) -> str:
    return IMPORT_URL.format(tournament_id=tournament_id)


def _default_row() -> dict:
    return {
        "Epreuve": "Messieurs P100",
        "Catégorie d'âge": "Senior",
        "Rang": "",
        "Nom J1": "Martin",
        "Prénom J1": "Julien",
        "Naissance J1": datetime.date(1994, 4, 2),
        "Licence J1": "LIC0000001",
        "Club J1": "TC Paris",
        "Classement J1": "250",
        "Courriel J1": "julien.martin@example.com",
        "Portable J1": "0612345678",
        "Nom J2": "Roux",
        "Prénom J2": "Quentin",
        "Naissance J2": datetime.date(1990, 1, 15),
        "Licence J2": "LIC0000002",
        "Club J2": "TC Lyon",
        "Classement J2": "310",
        "Courriel J2": "quentin.roux@example.com",
        "Portable J2": "0677889900",
        "Poids paire": "560.0",
    }


def make_xls_content(
    *rows: dict,
    headers: list[str] | None = None,
    sheet_name: str = SHEET_NAME,
    extra_sheets: list[str] | None = None,
) -> bytes:
    """Build an in-memory .xls workbook (xlwt) with a sheet of the given name.

    Each row dict is merged on top of `_default_row()` so tests only need to
    override the columns they actually care about. Pass header=None to use
    the real header row; pass an explicit `headers` list to simulate broken
    files. Date values (datetime.date) are written with a date-formatted
    cell so xlrd round-trips them as XL_CELL_DATE; strings are written as
    plain text cells (XL_CELL_TEXT).
    """
    workbook = xlwt.Workbook()
    for extra in extra_sheets or []:
        workbook.add_sheet(extra)
    sheet = workbook.add_sheet(sheet_name)

    header_row = headers if headers is not None else HEADERS
    for col, header in enumerate(header_row):
        sheet.write(0, col, header)

    for row_idx, overrides in enumerate(rows, start=1):
        row = {**_default_row(), **overrides}
        for col, header in enumerate(header_row):
            value = row.get(header, "")
            if isinstance(value, datetime.date):
                sheet.write(row_idx, col, value, DATE_FORMAT)
            else:
                sheet.write(row_idx, col, value)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def make_xls_number_content_with_numeric_license(
    license_j1: str, license_j2: str
) -> bytes:
    """Build a workbook where Licence J1 is written as a plain Excel number
    (e.g. 1234567), to verify no '.0' artifact leaks into the stored value.
    """
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet(SHEET_NAME)
    for col, header in enumerate(HEADERS):
        sheet.write(0, col, header)

    row = {**_default_row(), "Licence J1": license_j1, "Licence J2": license_j2}
    for col, header in enumerate(HEADERS):
        value = row.get(header, "")
        if header == "Licence J1":
            sheet.write(1, col, float(value))
        elif isinstance(value, datetime.date):
            sheet.write(1, col, value, DATE_FORMAT)
        else:
            sheet.write(1, col, value)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def make_xls_file(content: bytes, filename: str = "inscriptions.xls") -> io.BytesIO:
    f = io.BytesIO(content)
    f.name = filename
    return f


def make_xls_number_content(*rows: dict) -> bytes:
    """Build a workbook where Licence/Classement/Poids paire are written as
    Excel *numbers* (XL_CELL_NUMBER) instead of text, to test robustness.
    """
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet(SHEET_NAME)
    for col, header in enumerate(HEADERS):
        sheet.write(0, col, header)

    numeric_headers = {"Classement J1", "Classement J2", "Poids paire"}

    for row_idx, overrides in enumerate(rows, start=1):
        row = {**_default_row(), **overrides}
        for col, header in enumerate(HEADERS):
            value = row.get(header, "")
            if isinstance(value, datetime.date):
                sheet.write(row_idx, col, value, DATE_FORMAT)
            elif header in numeric_headers and value != "":
                sheet.write(row_idx, col, float(value))
            else:
                sheet.write(row_idx, col, value)

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
# TestXlsImportHappyPath
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsImportHappyPath:
    def test_xls_import_requires_auth(self, tournament):
        client = APIClient()
        content = make_xls_content()
        f = make_xls_file(content)
        response = client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 401

    def test_xls_import_success_creates_pair(self, auth_client, tournament):
        content = make_xls_content(
            {"Licence J1": "XLS0000001", "Licence J2": "XLS0000002"}
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert len(response.data) == 1

    def test_xls_import_creates_players_with_all_fields(self, auth_client, tournament):
        from apps.players.models import Player

        content = make_xls_content(
            {"Licence J1": "FULL0000001", "Licence J2": "FULL0000002"}
        )
        f = make_xls_file(content)
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

    def test_xls_import_sets_pair_weight(self, auth_client, tournament):
        from apps.players.models import Pair

        content = make_xls_content(
            {
                "Licence J1": "WEIGHT0001",
                "Licence J2": "WEIGHT0002",
                "Poids paire": "560.0",
            }
        )
        f = make_xls_file(content)
        auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        pair = Pair.objects.get(
            tournament=tournament,
            player1__license_number="WEIGHT0001",
            player2__license_number="WEIGHT0002",
        )
        assert pair.weight == 560.0

    def test_xls_import_birth_date_text_fallback(self, auth_client, tournament):
        """Naissance J1/J2 may come back as plain text JJ/MM/AAAA instead of a date cell."""
        from apps.players.models import Player

        content = make_xls_content(
            {
                "Licence J1": "TEXTDATE001",
                "Licence J2": "TEXTDATE002",
                "Naissance J1": "02/04/1994",
                "Naissance J2": "15/01/1990",
            }
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        p1 = Player.objects.get(license_number="TEXTDATE001")
        p2 = Player.objects.get(license_number="TEXTDATE002")
        assert p1.birth_date == datetime.date(1994, 4, 2)
        assert p2.birth_date == datetime.date(1990, 1, 15)

    def test_xls_import_ignores_epreuve_categorie_rang(self, auth_client, tournament):
        """Epreuve / Catégorie d'âge / Rang are read but never stored anywhere."""
        content = make_xls_content(
            {
                "Licence J1": "IGNORE0001",
                "Licence J2": "IGNORE0002",
                "Epreuve": "Some Event",
                "Catégorie d'âge": "Senior +35",
                "Rang": "12",
            }
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        # Sanity: nothing on Player/Pair references these values; if creation
        # succeeds with the normal expected fields, they were simply ignored.
        from apps.players.models import Player

        assert Player.objects.filter(license_number="IGNORE0001").exists()

    def test_xls_import_response_contains_all_tournament_pairs(
        self, auth_client, tournament
    ):
        from apps.players.tests.factories import PairFactory

        PairFactory(tournament=tournament)
        content = make_xls_content(
            {"Licence J1": "ALLPAIRS001", "Licence J2": "ALLPAIRS002"}
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert len(response.data) == 2


# ---------------------------------------------------------------------------
# TestXlsImportLicenseSeasonSuffix
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsImportLicenseSeasonSuffix:
    def test_license_season_suffix_is_stripped(self, auth_client, tournament):
        from apps.players.models import Player

        content = make_xls_content(
            {
                "Licence J1": "3271896H (2026)",
                "Licence J2": "LICNOSUFFIX002",
            }
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert Player.objects.filter(license_number="3271896H").exists()
        assert not Player.objects.filter(license_number="3271896H (2026)").exists()

    def test_license_without_suffix_is_unchanged(self, auth_client, tournament):
        from apps.players.models import Player

        content = make_xls_content(
            {
                "Licence J1": "LICNOSUFFIX001",
                "Licence J2": "LICNOSUFFIX002",
            }
        )
        f = make_xls_file(content)
        auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert Player.objects.filter(license_number="LICNOSUFFIX001").exists()

    def test_reimport_next_season_updates_same_player(self, auth_client, tournament):
        """Re-importing the same player next season (different year suffix)
        updates the existing Player rather than creating a duplicate."""
        from apps.players.models import Player

        content_2026 = make_xls_content(
            {
                "Licence J1": "3271896H (2026)",
                "Licence J2": "SEASONOTHER002",
                "Nom J1": "Martin",
            }
        )
        f1 = make_xls_file(content_2026)
        auth_client.post(
            import_url(tournament.id), data={"file": f1}, format="multipart"
        )
        assert Player.objects.filter(license_number="3271896H").count() == 1

        content_2027 = make_xls_content(
            {
                "Licence J1": "3271896H (2027)",
                "Licence J2": "SEASONOTHER002",
                "Nom J1": "MartinUpdated",
            }
        )
        f2 = make_xls_file(content_2027)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f2}, format="multipart"
        )
        assert response.status_code == 201
        assert Player.objects.filter(license_number="3271896H").count() == 1
        player = Player.objects.get(license_number="3271896H")
        assert player.last_name == "MartinUpdated"


# ---------------------------------------------------------------------------
# TestXlsImportCellTypeRobustness
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsImportCellTypeRobustness:
    def test_classement_weight_as_excel_numbers_no_dot_zero_artifact(
        self, auth_client, tournament
    ):
        """Classement/Poids paire written as Excel numbers (not text) must
        still parse without a trailing '.0' artifact on integer fields."""
        from apps.players.models import Pair, Player

        content = make_xls_number_content(
            {
                "Licence J1": "NUM0000001",
                "Licence J2": "NUM0000002",
                "Classement J1": "250",
                "Classement J2": "310",
                "Poids paire": "560.0",
            }
        )
        f = make_xls_file(content)
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

        workbook_bytes = make_xls_number_content_with_numeric_license(
            license_j1="1234567", license_j2="NUMLICOTHER002"
        )
        f = make_xls_file(workbook_bytes)
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

        content = make_xls_number_content(
            {
                "Licence J1": "NUMFLOAT001",
                "Licence J2": "NUMFLOAT002",
                "Poids paire": "560.5",
            }
        )
        f = make_xls_file(content)
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
# TestXlsImportPriorityRules
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsImportPriorityRules:
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
        content = make_xls_content(
            {
                "Licence J1": "PRIO0000001",
                "Licence J2": "PRIO0000002",
                "Classement J1": "999",
            }
        )
        f = make_xls_file(content)
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
        content = make_xls_content(
            {
                "Licence J1": "PRIO0000003",
                "Licence J2": "PRIO0000004",
                "Classement J1": "",
            }
        )
        f = make_xls_file(content)
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

        content = make_xls_content(
            {
                "Licence J1": "PRIO0000005",
                "Licence J2": "PRIO0000006",
                "Classement J1": "",
                "Classement J2": "",
            }
        )
        f = make_xls_file(content)
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

        content = make_xls_content(
            {
                "Licence J1": "WPRIO0000001",
                "Licence J2": "WPRIO0000002",
                "Poids paire": "999.0",
            }
        )
        f = make_xls_file(content)
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

        content = make_xls_content(
            {
                "Licence J1": "WPRIO0000003",
                "Licence J2": "WPRIO0000004",
                "Poids paire": "",
            }
        )
        f = make_xls_file(content)
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
        content = make_xls_content(
            {
                "Licence J1": "BPRIO0000001",
                "Licence J2": "BPRIO0000002",
                "Naissance J1": datetime.date(1999, 12, 31),
            }
        )
        f = make_xls_file(content)
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
        content = make_xls_content(
            {
                "Licence J1": "BPRIO0000003",
                "Licence J2": "BPRIO0000004",
                "Naissance J1": "",
            }
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        player = Player.objects.get(license_number="BPRIO0000003")
        assert player.birth_date == datetime.date(1980, 1, 1)


# ---------------------------------------------------------------------------
# TestXlsImportValidationErrors
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsImportValidationErrors:
    def test_no_file(self, auth_client, tournament):
        response = auth_client.post(
            import_url(tournament.id), data={}, format="multipart"
        )
        assert response.status_code == 400

    def test_wrong_extension(self, auth_client, tournament):
        f = io.BytesIO(b"not an xls file")
        f.name = "pairs.csv"
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_corrupt_unreadable_file(self, auth_client, tournament):
        f = io.BytesIO(b"this is not a valid xls binary content at all !!!")
        f.name = "inscriptions.xls"
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_missing_inscriptions_sheet_only_joueurs_sheet(
        self, auth_client, tournament
    ):
        workbook = xlwt.Workbook()
        workbook.add_sheet("Joueurs")
        buffer = io.BytesIO()
        workbook.save(buffer)
        f = make_xls_file(buffer.getvalue())
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_missing_inscriptions_sheet_unrelated_sheet_name(
        self, auth_client, tournament
    ):
        workbook = xlwt.Workbook()
        workbook.add_sheet("Feuille1")
        buffer = io.BytesIO()
        workbook.save(buffer)
        f = make_xls_file(buffer.getvalue())
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_missing_header_row(self, auth_client, tournament):
        workbook = xlwt.Workbook()
        workbook.add_sheet(SHEET_NAME)
        buffer = io.BytesIO()
        workbook.save(buffer)
        f = make_xls_file(buffer.getvalue())
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_invalid_header_row_missing_column(self, auth_client, tournament):
        broken_headers = [h for h in HEADERS if h != "Licence J1"]
        content = make_xls_content(
            {"Licence J2": "BADHEADER002"}, headers=broken_headers
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_missing_license_j1(self, auth_client, tournament):
        content = make_xls_content({"Licence J1": "", "Licence J2": "MISSLIC002"})
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_missing_license_j2(self, auth_client, tournament):
        content = make_xls_content({"Licence J1": "MISSLIC001", "Licence J2": ""})
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_duplicate_license_within_file(self, auth_client, tournament):
        content = make_xls_content(
            {"Licence J1": "DUPLIC001", "Licence J2": "DUPLIC002"},
            {"Licence J1": "DUPLIC001", "Licence J2": "DUPLIC003"},
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_invalid_birth_date_text(self, auth_client, tournament):
        content = make_xls_content(
            {
                "Licence J1": "BADDATE001",
                "Licence J2": "BADDATE002",
                "Naissance J1": "not-a-date",
            }
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_invalid_birth_date_text_for_player2(self, auth_client, tournament):
        """Same validation must apply to J2's birth date, not just J1's."""
        content = make_xls_content(
            {
                "Licence J1": "BADDATE003",
                "Licence J2": "BADDATE004",
                "Naissance J2": "not-a-date",
            }
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 400

    def test_header_only_file_succeeds_no_pairs_created(self, auth_client, tournament):
        from apps.players.models import Pair

        content = make_xls_content()  # no rows passed
        # make_xls_content with no rows means zero data rows are written.
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 201
        assert Pair.objects.filter(tournament=tournament).count() == 0

    def test_locked_tournament_started_returns_409(self, auth_client, tournament):
        from apps.players.models import Pair

        tournament.status = Tournament.Status.STARTED
        tournament.save()
        content = make_xls_content(
            {"Licence J1": "LOCKED0001", "Licence J2": "LOCKED0002"}
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 409
        assert not Pair.objects.filter(tournament=tournament).exists()

    def test_locked_tournament_finished_returns_409(self, auth_client, tournament):
        from apps.players.models import Pair

        tournament.status = Tournament.Status.FINISHED
        tournament.save()
        content = make_xls_content(
            {"Licence J1": "LOCKED0003", "Licence J2": "LOCKED0004"}
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 409
        assert not Pair.objects.filter(tournament=tournament).exists()

    def test_wrong_owner_tournament_returns_404(self, auth_client, other_tournament):
        content = make_xls_content()
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(other_tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, tournament):
        client = APIClient()
        content = make_xls_content()
        f = make_xls_file(content)
        response = client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# TestXlsImportAutoFFTMatching
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsImportAutoFFTMatching:
    """After an xls import, FFT ranking matching is automatically triggered
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

        content = make_xls_content(
            {
                "Nom J1": "Dupont",
                "Prénom J1": "Alice",
                "Licence J1": "AUTOFFT0001",
                "Classement J1": "",
                "Nom J2": "Bernard",
                "Prénom J2": "Bob",
                "Licence J2": "AUTOFFT0002",
                "Classement J2": "",
                "Poids paire": "",
            }
        )
        f = make_xls_file(content)
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

        content = make_xls_content(
            {
                "Nom J1": "Leroy",
                "Prénom J1": "Paul",
                "Licence J1": "NOOVERWRITE0001",
                "Classement J1": "50",
                "Nom J2": "Simon",
                "Prénom J2": "Jean",
                "Licence J2": "NOOVERWRITE0002",
                "Classement J2": "75",
            }
        )
        f = make_xls_file(content)
        response = auth_client.post(
            import_url(tournament.id), data={"file": f}, format="multipart"
        )

        assert response.status_code == 201
        p1 = Player.objects.get(license_number="NOOVERWRITE0001")
        p2 = Player.objects.get(license_number="NOOVERWRITE0002")
        assert p1.ranking == 50
        assert p2.ranking == 75


# ---------------------------------------------------------------------------
# TestXlsImportNonRegression
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestXlsImportNonRegression:
    def test_existing_pairs_not_in_file_are_preserved(self, auth_client, tournament):
        from apps.players.models import Pair
        from apps.players.tests.factories import PairFactory

        existing_pair = PairFactory(tournament=tournament)
        existing_pair_id = existing_pair.id

        content = make_xls_content(
            {"Licence J1": "NONREG0001", "Licence J2": "NONREG0002"}
        )
        f = make_xls_file(content)
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

        content = make_xls_content(
            {
                "Licence J1": "REIMPORT0001",
                "Licence J2": "REIMPORT0002",
                "Poids paire": "300.0",
            }
        )
        f1 = make_xls_file(content)
        auth_client.post(
            import_url(tournament.id), data={"file": f1}, format="multipart"
        )
        assert Pair.objects.filter(tournament=tournament).count() == 1

        content2 = make_xls_content(
            {
                "Licence J1": "REIMPORT0001",
                "Licence J2": "REIMPORT0002",
                "Poids paire": "450.0",
                "Club J1": "Nouveau Club",
            }
        )
        f2 = make_xls_file(content2)
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
