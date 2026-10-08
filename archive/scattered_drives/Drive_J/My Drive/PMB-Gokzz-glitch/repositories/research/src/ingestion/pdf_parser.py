"""
PDF Ledger Parser
=================
Extracts text from PDF files (invoices, ledgers, payment records) and
converts each page into one or more :class:`Communication` objects.

The parser attempts to detect and parse dates inside the extracted text so
that a meaningful timestamp can be attached to each document / page.  If no
date can be found the *fallback_date* parameter is used; if that is also
absent the page is skipped.

Dependencies
------------
* ``pdfminer.six`` – PDF text extraction.
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import List, Optional

from src.models.communication import Communication, SourceType


# ---------------------------------------------------------------------------
# Date-detection patterns inside PDF text
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"), "%d/%m/%Y"),
    # YYYY-MM-DD (ISO 8601)
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "%Y-%m-%d"),
    # DD Month YYYY  e.g. "15 March 2024"
    (
        re.compile(
            r"\b(\d{1,2})\s+"
            r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
            r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
            r"|Dec(?:ember)?)\s+(\d{4})\b",
            re.IGNORECASE,
        ),
        "%d %B %Y",
    ),
    # Month DD, YYYY  e.g. "March 15, 2024"
    (
        re.compile(
            r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
            r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
            r"|Dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})\b",
            re.IGNORECASE,
        ),
        "%B %d %Y",
    ),
]

_MONTH_ABBREV = {
    "jan": "January", "feb": "February", "mar": "March",
    "apr": "April", "may": "May", "jun": "June",
    "jul": "July", "aug": "August", "sep": "September",
    "oct": "October", "nov": "November", "dec": "December",
}


def _normalise_month(text: str) -> str:
    """Expand abbreviated month names to their full form."""
    key = text[:3].lower()
    return _MONTH_ABBREV.get(key, text)


def _find_first_date(text: str) -> Optional[datetime]:
    """Return the first recognisable date found in *text*."""
    for pattern, fmt in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue

        groups = match.groups()
        # Normalise month abbreviation where needed
        normalised = tuple(_normalise_month(g) for g in groups)
        date_str = " ".join(normalised)

        # Build format string matching the number of groups
        if fmt == "%d/%m/%Y":
            # groups: day, month, year  (all numeric)
            try:
                return datetime(int(groups[2]), int(groups[1]), int(groups[0]))
            except ValueError:
                # Maybe MM/DD/YYYY; swap month and day
                try:
                    return datetime(int(groups[2]), int(groups[0]), int(groups[1]))
                except ValueError:
                    pass

        elif fmt == "%Y-%m-%d":
            try:
                return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
            except ValueError:
                pass

        else:
            # Text-based month patterns – normalise to full month name first
            for real_fmt in (
                "%d %B %Y",
                "%B %d %Y",
                "%-d %B %Y",
                "%B %-d %Y",
            ):
                try:
                    return datetime.strptime(date_str, real_fmt)
                except (ValueError, AttributeError):
                    pass
    return None


class PDFParser:
    """
    Parse a PDF file and return a list of :class:`Communication` objects.

    Each page of the PDF is treated as one logical document segment.  An
    attempt is made to detect the earliest date in each page's text; this
    becomes the ``timestamp`` of the resulting :class:`Communication`.

    Parameters
    ----------
    fallback_date:
        Used as the timestamp when no date can be detected in a page.
        If *None*, pages without a detectable date are skipped.
    """

    def __init__(self, fallback_date: Optional[datetime] = None) -> None:
        self.fallback_date = fallback_date

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, filepath: str) -> List[Communication]:
        """Extract text from *filepath* and return parsed :class:`Communication` objects."""
        try:
            from pdfminer.high_level import extract_pages
            from pdfminer.layout import LTTextContainer
        except ImportError as exc:
            raise ImportError(
                "pdfminer.six is required for PDF parsing. "
                "Install it with:  pip install pdfminer.six"
            ) from exc

        communications: List[Communication] = []

        for page_num, page_layout in enumerate(extract_pages(filepath), start=1):
            page_text_parts: List[str] = []
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    page_text_parts.append(element.get_text())

            page_text = "\n".join(page_text_parts).strip()
            if not page_text:
                continue

            comm = self._build_communication(page_text, page_num, filepath)
            if comm:
                communications.append(comm)

        return communications

    def parse_bytes(
        self, pdf_bytes: bytes, source_name: str = "pdf"
    ) -> List[Communication]:
        """Parse PDF from raw bytes (useful when the file lives in memory)."""
        try:
            from pdfminer.high_level import extract_pages
            from pdfminer.layout import LTTextContainer
        except ImportError as exc:
            raise ImportError(
                "pdfminer.six is required for PDF parsing. "
                "Install it with:  pip install pdfminer.six"
            ) from exc

        communications: List[Communication] = []

        for page_num, page_layout in enumerate(
            extract_pages(io.BytesIO(pdf_bytes)), start=1
        ):
            page_text_parts: List[str] = []
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    page_text_parts.append(element.get_text())

            page_text = "\n".join(page_text_parts).strip()
            if not page_text:
                continue

            comm = self._build_communication(page_text, page_num, source_name)
            if comm:
                communications.append(comm)

        return communications

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_communication(
        self, text: str, page_num: int, source_name: str
    ) -> Optional[Communication]:
        timestamp = _find_first_date(text) or self.fallback_date
        if timestamp is None:
            return None

        return Communication(
            text=text,
            timestamp=timestamp,
            sender=source_name,
            source_type=SourceType.PDF,
            metadata={"page": page_num, "source_file": source_name},
        )
