"""
Email Thread Parser
===================
Parses plain-text email threads (RFC 2822 / mbox-like format) into
:class:`Communication` objects.

Supported input types
---------------------
* Raw RFC 2822 email text (single message or a quoted thread).
* A multi-message mbox file (messages separated by ``From `` lines).

For quoted / forwarded content the parser extracts only the top-level reply
and ignores nested quotation lines starting with ``>``.
"""

from __future__ import annotations

import email
import re
from datetime import datetime
from email import policy
from email.utils import parsedate_to_datetime
from typing import List, Optional

from src.models.communication import Communication, SourceType


# Regex to identify quoted lines in a plain-text reply
_QUOTE_LINE = re.compile(r"^\s*>")
# "On ... wrote:" separator common in Gmail / Outlook
_QUOTE_HEADER = re.compile(
    r"^On\s+.+wrote:\s*$", re.IGNORECASE | re.DOTALL
)
_MBOX_SEPARATOR = re.compile(r"^From\s+\S+.*\d{4}\s*$")


def _strip_quoted_text(body: str) -> str:
    """Remove quoted reply lines from an email body."""
    lines = []
    for line in body.splitlines():
        if _QUOTE_LINE.match(line):
            continue
        if _QUOTE_HEADER.match(line.strip()):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _extract_sender_address(from_header: str) -> str:
    """Return just the email address from a 'From' header value."""
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1)
    return from_header.strip()


class EmailParser:
    """Parse email threads / mbox files into :class:`Communication` objects."""

    def parse_file(self, filepath: str) -> List[Communication]:
        """Read *filepath* and return parsed email messages."""
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        return self.parse_text(raw)

    def parse_text(self, raw_text: str) -> List[Communication]:
        """
        Parse *raw_text* which may be a single RFC 2822 message or an mbox
        file containing multiple messages.  Returns a list of
        :class:`Communication` objects ordered by timestamp.
        """
        # Split mbox into individual messages
        raw_messages = self._split_mbox(raw_text)
        communications: List[Communication] = []
        for raw_msg in raw_messages:
            comm = self._parse_single(raw_msg.strip())
            if comm:
                communications.append(comm)

        # Sort chronologically
        communications.sort(key=lambda c: c.timestamp)
        return communications

    # ------------------------------------------------------------------

    def _split_mbox(self, text: str) -> List[str]:
        """Split an mbox file into individual raw message strings."""
        messages: List[str] = []
        current_lines: List[str] = []

        for line in text.splitlines(keepends=True):
            if _MBOX_SEPARATOR.match(line) and current_lines:
                messages.append("".join(current_lines))
                current_lines = []
            current_lines.append(line)

        if current_lines:
            messages.append("".join(current_lines))

        return [m for m in messages if m.strip()]

    def _parse_single(self, raw_msg: str) -> Optional[Communication]:
        """Parse a single RFC 2822 message string."""
        try:
            msg = email.message_from_string(raw_msg, policy=policy.default)
        except Exception:
            return None

        # Timestamp
        date_header = msg.get("Date", "")
        timestamp = self._parse_date(date_header)
        if timestamp is None:
            return None

        # Sender
        from_header = msg.get("From", "")
        sender = _extract_sender_address(str(from_header))

        # Body
        body = self._get_body(msg)
        if not body:
            return None

        body = _strip_quoted_text(body)

        return Communication(
            text=body,
            timestamp=timestamp,
            sender=sender,
            source_type=SourceType.EMAIL,
            metadata={
                "subject": str(msg.get("Subject", "")),
                "to": str(msg.get("To", "")),
                "message_id": str(msg.get("Message-ID", "")),
            },
        )

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Parse an RFC 2822 date string into a datetime."""
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            pass
        # Fallback: strip timezone name and try again
        cleaned = re.sub(r"\s+\([^)]+\)$", "", date_str.strip())
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _get_body(msg: email.message.Message) -> str:
        """Extract plain-text body from an email message object."""
        body_parts: List[str] = []
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                if ctype == "text/plain" and "attachment" not in disposition:
                    try:
                        body_parts.append(
                            part.get_content()
                            if hasattr(part, "get_content")
                            else part.get_payload(decode=True).decode(
                                part.get_content_charset() or "utf-8",
                                errors="replace",
                            )
                        )
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    body_parts.append(
                        payload.decode(
                            msg.get_content_charset() or "utf-8",
                            errors="replace",
                        )
                    )
                elif isinstance(msg.get_payload(), str):
                    body_parts.append(msg.get_payload())
            except Exception:
                pass

        return "\n".join(body_parts).strip()
