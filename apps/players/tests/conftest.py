"""Fixtures for players app tests."""
import os

import pytest
from fpdf import FPDF


# ---------------------------------------------------------------------------
# Paths to the real FFT ranking PDFs (mounted into the container via docker)
# ---------------------------------------------------------------------------

_REAL_MEN_PDF = "input_pdf/classement_padel_france_homme_2026_03_mars.pdf"
_REAL_WOMEN_PDF = "input_pdf/classement_padel_france_femme_2026_03_mars.pdf"


@pytest.fixture(scope="session")
def men_pdf_path() -> str:
    """Absolute path to the real FFT men's ranking PDF."""
    if not os.path.exists(_REAL_MEN_PDF):
        pytest.skip(f"Real men's PDF not found: {_REAL_MEN_PDF}")
    return _REAL_MEN_PDF


@pytest.fixture(scope="session")
def women_pdf_path() -> str:
    """Absolute path to the real FFT women's ranking PDF."""
    if not os.path.exists(_REAL_WOMEN_PDF):
        pytest.skip(f"Real women's PDF not found: {_REAL_WOMEN_PDF}")
    return _REAL_WOMEN_PDF


# ---------------------------------------------------------------------------
# Synthetic PDFs for error-case testing (fpdf2 — no FFT data needed)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def no_header_pdf_path(tmp_path_factory) -> str:
    """PDF with no recognisable FFT column header."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Random content with no FFT header at all")
    path = tmp_path_factory.mktemp("pdfs") / "no_header.pdf"
    path.write_bytes(bytes(pdf.output()))
    return str(path)


@pytest.fixture(scope="session")
def corrupted_pdf_path(tmp_path_factory) -> str:
    """A file whose bytes are not a valid PDF."""
    path = tmp_path_factory.mktemp("pdfs") / "corrupted.pdf"
    path.write_bytes(b"this is not a pdf file at all !!!")
    return str(path)
