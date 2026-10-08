"""
Tests for the data ingestion parsers (WhatsApp, Email, PDF date detection).
"""

import pytest
from datetime import datetime

from src.ingestion.whatsapp_parser import WhatsAppParser, _parse_datetime
from src.ingestion.email_parser import EmailParser
from src.ingestion.pdf_parser import _find_first_date
from src.models.communication import SourceType


class TestWhatsAppParser:
    @pytest.fixture
    def parser(self):
        return WhatsAppParser()

    # --- Android format ---

    def test_android_24h_basic(self, parser):
        text = "14/03/2024, 09:45 - Alice: Hello Bob."
        comms = parser.parse_text(text)
        assert len(comms) == 1
        assert comms[0].sender == "Alice"
        assert comms[0].text == "Hello Bob."
        assert comms[0].source_type == SourceType.WHATSAPP
        assert comms[0].timestamp == datetime(2024, 3, 14, 9, 45)

    def test_android_12h_am(self, parser):
        text = "03/14/24, 9:45 AM - Bob: Payment done."
        comms = parser.parse_text(text)
        assert len(comms) == 1
        assert comms[0].sender == "Bob"

    def test_ios_format(self, parser):
        text = "[14/03/2024, 09:45:30 AM] Alice: Sending cheque now."
        comms = parser.parse_text(text)
        assert len(comms) == 1
        assert comms[0].sender == "Alice"
        assert comms[0].text == "Sending cheque now."

    def test_multiple_messages(self, parser):
        text = (
            "14/03/2024, 09:45 - Alice: First message.\n"
            "14/03/2024, 09:50 - Bob: Second message."
        )
        comms = parser.parse_text(text)
        assert len(comms) == 2

    def test_multiline_message(self, parser):
        text = (
            "14/03/2024, 09:45 - Alice: Line one.\n"
            "This is line two.\n"
            "14/03/2024, 09:50 - Bob: Next message."
        )
        comms = parser.parse_text(text)
        assert len(comms) == 2
        assert "line two" in comms[0].text

    def test_empty_text(self, parser):
        comms = parser.parse_text("")
        assert comms == []

    def test_sample_debt_file(self, parser, tmp_path):
        content = (
            "14/02/2024, 10:15 - Rajesh: Invoice INV-001 is outstanding.\n"
            "14/02/2024, 10:20 - Priya: I will send the cheque for the dues.\n"
        )
        f = tmp_path / "chat.txt"
        f.write_text(content, encoding="utf-8")
        comms = parser.parse_file(str(f))
        assert len(comms) == 2

    def test_metadata_present(self, parser):
        text = "14/03/2024, 09:45 - Alice: Hello."
        comms = parser.parse_text(text)
        assert "raw_date" in comms[0].metadata
        assert "raw_time" in comms[0].metadata


class TestParseDatetime:
    def test_dd_mm_yyyy_24h(self):
        result = _parse_datetime("14/03/2024", "09:45")
        assert result == datetime(2024, 3, 14, 9, 45)

    def test_dd_mm_yy_12h(self):
        result = _parse_datetime("14/03/24", "9:45 AM")
        assert result == datetime(2024, 3, 14, 9, 45)

    def test_invalid_returns_none(self):
        result = _parse_datetime("not-a-date", "not-a-time")
        assert result is None


class TestEmailParser:
    @pytest.fixture
    def parser(self):
        return EmailParser()

    def test_single_message(self, parser):
        raw = (
            "From: alice@example.com\n"
            "To: bob@example.com\n"
            "Date: Mon, 05 Feb 2024 09:00:00 +0530\n"
            "Subject: Payment Reminder\n"
            "\n"
            "Dear Bob, please clear the outstanding dues.\n"
        )
        comms = parser.parse_text(raw)
        assert len(comms) == 1
        assert comms[0].sender == "alice@example.com"
        assert "outstanding dues" in comms[0].text
        assert comms[0].source_type == SourceType.EMAIL

    def test_sender_in_angle_brackets(self, parser):
        raw = (
            "From: Alice Smith <alice@example.com>\n"
            "To: bob@example.com\n"
            "Date: Mon, 05 Feb 2024 09:00:00 +0530\n"
            "Subject: Test\n"
            "\n"
            "Body text here.\n"
        )
        comms = parser.parse_text(raw)
        assert comms[0].sender == "alice@example.com"

    def test_metadata_has_subject(self, parser):
        raw = (
            "From: alice@example.com\n"
            "To: bob@example.com\n"
            "Date: Mon, 05 Feb 2024 09:00:00 +0530\n"
            "Subject: Invoice Reminder\n"
            "\n"
            "Test body.\n"
        )
        comms = parser.parse_text(raw)
        assert comms[0].metadata["subject"] == "Invoice Reminder"

    def test_no_date_skipped(self, parser):
        raw = (
            "From: alice@example.com\n"
            "To: bob@example.com\n"
            "Subject: No date\n"
            "\n"
            "Body.\n"
        )
        comms = parser.parse_text(raw)
        assert comms == []

    def test_mbox_multiple_messages(self, parser):
        raw = (
            "From alice@example.com Mon Feb 05 09:00:00 2024\n"
            "From: alice@example.com\n"
            "To: bob@example.com\n"
            "Date: Mon, 05 Feb 2024 09:00:00 +0530\n"
            "Subject: First\n"
            "\n"
            "First email body.\n"
            "\n"
            "From bob@example.com Mon Feb 06 10:00:00 2024\n"
            "From: bob@example.com\n"
            "To: alice@example.com\n"
            "Date: Tue, 06 Feb 2024 10:00:00 +0530\n"
            "Subject: Second\n"
            "\n"
            "Second email body.\n"
        )
        comms = parser.parse_text(raw)
        assert len(comms) == 2

    def test_sorted_chronologically(self, parser):
        raw = (
            "From bob@example.com Mon Feb 06 10:00:00 2024\n"
            "From: bob@example.com\n"
            "To: alice@example.com\n"
            "Date: Tue, 06 Feb 2024 10:00:00 +0530\n"
            "Subject: Second\n"
            "\n"
            "Second email body.\n"
            "\n"
            "From alice@example.com Mon Feb 05 09:00:00 2024\n"
            "From: alice@example.com\n"
            "To: bob@example.com\n"
            "Date: Mon, 05 Feb 2024 09:00:00 +0530\n"
            "Subject: First\n"
            "\n"
            "First email body.\n"
        )
        comms = parser.parse_text(raw)
        assert len(comms) == 2
        assert comms[0].timestamp < comms[1].timestamp

    def test_sample_eml_file(self, parser, tmp_path):
        content = (
            "From: rajesh@example.com\n"
            "To: priya@example.com\n"
            "Date: Mon, 05 Feb 2024 09:00:00 +0530\n"
            "Subject: Outstanding Payment\n"
            "\n"
            "Please clear the outstanding balance of Rs. 2,50,000.\n"
        )
        f = tmp_path / "email.eml"
        f.write_text(content, encoding="utf-8")
        comms = parser.parse_file(str(f))
        assert len(comms) == 1


class TestPDFDateDetection:
    """Test the _find_first_date helper used by PDFParser."""

    def test_dd_mm_yyyy_slash(self):
        result = _find_first_date("Invoice Date: 15/03/2024")
        assert result == datetime(2024, 3, 15)

    def test_dd_mm_yyyy_hyphen(self):
        result = _find_first_date("Date: 15-03-2024")
        assert result == datetime(2024, 3, 15)

    def test_iso_8601(self):
        result = _find_first_date("Created: 2024-03-15")
        assert result == datetime(2024, 3, 15)

    def test_text_date_full(self):
        result = _find_first_date("Invoice Date: 15 March 2024")
        assert result == datetime(2024, 3, 15)

    def test_no_date_returns_none(self):
        result = _find_first_date("No date information here at all.")
        assert result is None

    def test_picks_first_date(self):
        result = _find_first_date("First: 01/01/2024. Second: 15/03/2024.")
        assert result == datetime(2024, 1, 1)
