"""
WhatsApp Chat Export Parser
===========================
Parses the plain-text format produced by WhatsApp's "Export Chat" feature.

Supported format examples
--------------------------
Android (24-hour):
    14/03/2024, 09:45 - Alice: Here is the cheque for the invoice.

Android (12-hour):
    3/14/24, 9:45 AM - Bob: Payment done.

iOS (12-hour):
    [14/03/2024, 09:45:30 AM] Alice: Sending cheque now.

System messages (no colon after name) are silently skipped.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from src.models.communication import Communication, SourceType


# ---------------------------------------------------------------------------
# Compiled patterns for the two major WhatsApp date/time formats
# ---------------------------------------------------------------------------

# Android: "14/03/2024, 09:45 - Sender: message"
# Also handles "14/03/24, 9:45 AM - Sender: message"
_ANDROID_PATTERN = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?)\s+-\s+"
    r"(?P<sender>[^:]+):\s+(?P<text>.+)$",
    re.IGNORECASE,
)

# iOS: "[14/03/2024, 09:45:30 AM] Sender: message"
_IOS_PATTERN = re.compile(
    r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?)\]\s+"
    r"(?P<sender>[^:]+):\s+(?P<text>.+)$",
    re.IGNORECASE,
)

_DATE_FORMATS = [
    "%d/%m/%Y",
    "%d/%m/%y",
    "%m/%d/%Y",
    "%m/%d/%y",
]
_TIME_FORMATS = [
    "%H:%M",
    "%H:%M:%S",
    "%I:%M %p",
    "%I:%M:%S %p",
    "%I:%M%p",
    "%I:%M:%S%p",
]


def _parse_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """Try multiple date + time format combinations and return the first match."""
    time_str = time_str.strip()
    for dfmt in _DATE_FORMATS:
        for tfmt in _TIME_FORMATS:
            try:
                return datetime.strptime(f"{date_str} {time_str}", f"{dfmt} {tfmt}")
            except ValueError:
                continue
    return None


class WhatsAppParser:
    """Parse a WhatsApp chat export and return a list of :class:`Communication` objects."""

    def parse_file(self, filepath: str) -> List[Communication]:
        """Read *filepath* and return parsed messages."""
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        return self.parse_text(raw)

    def parse_text(self, raw_text: str) -> List[Communication]:
        """
        Parse *raw_text* (the full content of a WhatsApp export) and return a
        list of :class:`Communication` objects ordered by timestamp.
        """
        communications: List[Communication] = []
        current: Optional[dict] = None

        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue

            match = _ANDROID_PATTERN.match(line) or _IOS_PATTERN.match(line)
            if match:
                # Flush previous message
                if current:
                    comm = self._build(current)
                    if comm:
                        communications.append(comm)

                ts = _parse_datetime(match.group("date"), match.group("time"))
                current = {
                    "date": match.group("date"),
                    "time": match.group("time"),
                    "timestamp": ts,
                    "sender": match.group("sender").strip(),
                    "text": match.group("text").strip(),
                }
            elif current is not None:
                # Continuation line (multi-line message)
                current["text"] += " " + line

        # Flush last message
        if current:
            comm = self._build(current)
            if comm:
                communications.append(comm)

        return communications

    # ------------------------------------------------------------------

    @staticmethod
    def _build(data: dict) -> Optional[Communication]:
        ts = data.get("timestamp")
        if ts is None:
            return None
        return Communication(
            text=data["text"],
            timestamp=ts,
            sender=data["sender"],
            source_type=SourceType.WHATSAPP,
            metadata={"raw_date": data["date"], "raw_time": data["time"]},
        )
