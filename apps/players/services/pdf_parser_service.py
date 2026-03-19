"""FFT ranking PDF parser using pypdfium2."""
import re
import unicodedata
from dataclasses import dataclass

import pypdfium2 as pdfium

from apps.tournaments.models import Tournament

# Y-tolerance in PDF points for grouping characters into the same visual row.
# Space characters sit lower on the baseline than uppercase letters, so a
# tolerance of ~8pt is needed.
ROW_Y_TOLERANCE = 8.0

# Minimum X-gap (PDF points) between character right-edge and next character
# left-edge to consider them as belonging to separate words.
WORD_GAP_THRESHOLD = 2.0

# Keywords that must appear (normalized) in the FFT column header row.
HEADER_KEYWORDS = {"nom", "prenom", "ligue", "points"}

# Regex to detect a standalone 3-letter uppercase country code (FRA, ESP, …).
COUNTRY_CODE_RE = re.compile(r"\b([A-Z]{3})\b")

# Numeric patterns used in row parsing.
SIGNED_INT_RE = re.compile(r"^[+-]?\d+$")
PURE_INT_RE = re.compile(r"^\d+$")

# Special overrides for league names whose PDF spelling differs from
# Tournament.League values even after accent/hyphen normalisation.
LEAGUE_OVERRIDES: dict[str, str] = {
    "provence alpes cote d azur": "Provence-Alpes-Côtes d'Azur",
    "provence alpes cotes d azur": "Provence-Alpes-Côtes d'Azur",
    "guadeloupe st martin st barth": "Guadeloupe",
    "guadeloupe saint martin saint barthelemy": "Guadeloupe",
}


class PDFParseError(Exception):
    pass


class PDFFormatUnknownError(Exception):
    pass


@dataclass
class ParsedRankingEntry:
    last_name: str
    first_name: str
    ranking: int
    points: float | None
    league: str


# ---------------------------------------------------------------------------
# Text normalisation helpers
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    """Lowercase + strip accents + normalise hyphens/apostrophes → spaces."""
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    s = re.sub(r"[-']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_league(raw: str) -> str:
    """Match a raw league string to a Tournament.League value.

    Matching is case-insensitive, accent-insensitive, and hyphen-tolerant.
    """
    normalized = _normalize(raw)
    if normalized in LEAGUE_OVERRIDES:
        return LEAGUE_OVERRIDES[normalized]
    for league in Tournament.League:
        if _normalize(league.value) == normalized:
            return league.value
    return ""


def _normalize_row_numbers(text: str) -> str:
    """Remove NBSP (\\xa0) thousand separators from digit sequences."""
    return re.sub(r"(\d)\xa0(\d)", r"\1\2", text)


# ---------------------------------------------------------------------------
# Character-level PDF extraction
# ---------------------------------------------------------------------------


def _extract_page_rows(page: pdfium.PdfPage) -> list[list[dict]]:
    """Extract character rows (grouped by Y position) for a single PDF page.

    Each row is a list of character dicts sorted by X, with keys:
      text (str), x (float), x2 (float), y (float, top-down from page top).
    """
    page_height = page.get_height()
    textpage = page.get_textpage()
    try:
        count = textpage.count_chars()

        chars: list[dict] = []
        for i in range(count):
            box = textpage.get_charbox(i, loose=False)
            chars.append(
                {
                    "text": textpage.get_text_range(i, 1),
                    "x": box[0],
                    "x2": box[2],
                    # Flip Y: small value = near top of page.
                    "y": page_height - box[3],
                }
            )

        return _group_chars_into_rows(chars)
    finally:
        textpage.close()


def _group_chars_into_rows(chars: list[dict]) -> list[list[dict]]:
    """Group characters into rows by Y coordinate (tolerance ROW_Y_TOLERANCE)."""
    if not chars:
        return []

    sorted_chars = sorted(chars, key=lambda c: c["y"])
    rows: list[list[dict]] = []
    current_row: list[dict] = [sorted_chars[0]]
    row_y_ref: float = sorted_chars[0]["y"]

    for ch in sorted_chars[1:]:
        if abs(ch["y"] - row_y_ref) <= ROW_Y_TOLERANCE:
            current_row.append(ch)
        else:
            rows.append(sorted(current_row, key=lambda c: c["x"]))
            current_row = [ch]
            row_y_ref = ch["y"]

    if current_row:
        rows.append(sorted(current_row, key=lambda c: c["x"]))

    return rows


def _row_to_text(row: list[dict]) -> str:
    """Concatenate all characters in a row (already sorted by X)."""
    return "".join(c["text"] for c in row)


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------


def _is_header_row(row_text: str) -> bool:
    """Return True if this row is the FFT ranking column header.

    The real header is: # ± Nom Prénom Points Pays Ligue Assimilé
    At least 3 of the 4 keywords must be present after normalisation.
    """
    lowered = _normalize(row_text)
    found = sum(1 for kw in HEADER_KEYWORDS if kw in lowered)
    return found >= 3


def _parse_name(name_str: str) -> tuple[str, str]:
    """Split 'LASTNAME Firstname' into (last_name, first_name).

    All-uppercase tokens (after stripping punctuation) → last name.
    First mixed-case token and everything after → first name.
    """
    parts = name_str.split()
    if not parts:
        return ("", "")

    last_name_parts: list[str] = []
    first_name_parts: list[str] = []
    switched = False

    for part in parts:
        clean = re.sub(r"[^a-zA-ZÀ-ÿ]", "", part)
        if not switched and clean and clean.upper() == clean:
            last_name_parts.append(part)
        else:
            switched = True
            first_name_parts.append(part)

    if not last_name_parts:
        last_name_parts = [parts[0]]
        first_name_parts = parts[1:]

    return " ".join(last_name_parts), " ".join(first_name_parts)


def _parse_league_from_after(after: str) -> str:
    """Extract the league name from the text that follows the country code.

    The PDF row format (after country) is:
      - Short form (early pages):  «nb_tournois [assimilé] LIGUE [Oui]»
      - Long form (later pages):   «total_pts\\r\\nnb_tournois LIGUE [Oui]»

    Strategy: take the last segment (after any \\r\\n), strip leading numbers,
    strip trailing "Oui", then normalise the remaining words as a league.
    """
    parts = re.split(r"\r?\n", after.strip())
    ligue_part = parts[-1] if parts else after

    tokens = ligue_part.split()
    # Remove leading numbers (nb_tournois, sub-scores, etc.)
    while tokens and re.match(r"^-?\d+$", tokens[0]):
        tokens = tokens[1:]
    # Remove trailing assimilé flag
    if tokens and tokens[-1] == "Oui":
        tokens = tokens[:-1]

    return _normalize_league(" ".join(tokens))


def _parse_entry_from_row(row: list[dict]) -> ParsedRankingEntry | None:
    """Parse a single character row into a ParsedRankingEntry.

    Returns None if the row is not a valid player data row.

    Row text format (after NBSP normalisation):
      {rank} [{±}] {NOM} {Prénom} [{Points}] {PAYS(3-letters)} {rest}

    The column order matches the FFT header: # ± Nom Prénom Points Pays Ligue …
    - rank   : first token (always positive integer)
    - ±      : second token if signed integer (optional, may be absent)
    - Points : last integer token before the country code (optional)
    - PAYS   : 3-letter uppercase country code used as the column anchor
    - Ligue  : extracted from the text that follows the country code
    """
    row_text = _row_to_text(row)
    # Remove NBSP thousand separators embedded in numbers (e.g. 13\xa0296 → 13296)
    text = _normalize_row_numbers(row_text)

    # Locate the 3-letter country code — our column anchor.
    country_match = COUNTRY_CODE_RE.search(text)
    if not country_match:
        return None

    before = text[: country_match.start()].strip()
    after = text[country_match.end() :].strip()

    before_tokens = before.split()
    if len(before_tokens) < 2:
        # Need at least: rank + name
        return None

    # First token = rank (#)
    try:
        ranking = int(before_tokens[0])
    except ValueError:
        return None

    remaining = before_tokens[1:]

    # Skip the ± column if it looks like a signed integer (e.g. -22, 0, 1080).
    if remaining and SIGNED_INT_RE.match(remaining[0]):
        remaining = remaining[1:]

    if not remaining:
        return None

    # Pop all trailing pure-integer tokens from the name block.
    # The FFT column order is: … Nom Prénom | Points | Meilleur class. | Pays …
    # Points is the FIRST trailing number (closest to the name); Meilleur class.
    # is the second.  We keep only Points; the rest are discarded.
    trailing_numbers: list[str] = []
    while remaining and PURE_INT_RE.match(remaining[-1]):
        trailing_numbers.insert(0, remaining.pop())

    points: float | None = None
    if trailing_numbers:
        try:
            points = float(trailing_numbers[0])
        except ValueError:
            pass

    if not remaining:
        return None

    # Remaining tokens = NOM + Prénom
    last_name, first_name = _parse_name(" ".join(remaining))
    if not last_name:
        return None

    league = _parse_league_from_after(after)

    return ParsedRankingEntry(
        last_name=last_name,
        first_name=first_name,
        ranking=ranking,
        points=points,
        league=league,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_fft_pdf(pdf_path: str) -> list[ParsedRankingEntry]:
    """Parse an FFT ranking PDF and return a list of ParsedRankingEntry.

    Each page is processed independently (prevents Y-coordinate collisions
    between pages and avoids loading all characters into memory at once).

    Raises:
        PDFParseError: if the file cannot be opened as a valid PDF.
        PDFFormatUnknownError: if no recognisable FFT header row is found.
    """
    try:
        doc = pdfium.PdfDocument(pdf_path)
    except Exception as e:
        raise PDFParseError(f"Cannot open PDF: {e}") from e

    entries: list[ParsedRankingEntry] = []
    header_found = False

    for page in doc:
        try:
            rows = _extract_page_rows(page)
        finally:
            page.close()

        for row in rows:
            row_text = _row_to_text(row)

            if not header_found:
                if _is_header_row(row_text):
                    header_found = True
                # Skip rows until the header has been found.
                continue

            entry = _parse_entry_from_row(row)
            if entry is not None:
                entries.append(entry)

    if not header_found:
        raise PDFFormatUnknownError(
            "No FFT ranking header found "
            "(expected columns: Nom, Prénom, Points, Ligue)"
        )

    return entries
