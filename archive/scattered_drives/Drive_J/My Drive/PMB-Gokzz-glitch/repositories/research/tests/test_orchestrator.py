"""
Integration tests for the Orchestrator.
"""

import pytest
from datetime import datetime

from src.orchestrator import Orchestrator
from src.models.communication import ChequeContext


@pytest.fixture
def orchestrator():
    return Orchestrator()


WHATSAPP_DEBT = """
14/02/2024, 10:15 - Rajesh: Invoice INV-2024-0145 is outstanding. Balance due ₹2,50,000.
14/02/2024, 10:20 - Priya: I acknowledge the outstanding dues. I will issue a cheque.
14/02/2024, 10:25 - Rajesh: Please ensure payment against Invoice No. INV-2024-0145.
"""

WHATSAPP_ADVANCE = """
01/03/2024, 09:30 - Amit: Here is the advance payment for the furniture order before delivery.
01/03/2024, 09:35 - Sunita: Received. This is advance before goods are dispatched.
"""

WHATSAPP_SECURITY = """
01/03/2024, 09:30 - Amit: I am giving you a security cheque. Please do not deposit it.
05/03/2024, 14:05 - Sunita: Confirmed, this PDC is held as security.
"""

EMAIL_DEBT = """From: rajesh@example.com
To: priya@example.com
Date: Mon, 05 Feb 2024 09:00:00 +0530
Subject: Outstanding Payment

Dear Priya, please clear the outstanding balance due on Invoice INV-001.
"""


class TestOrchestratorAnalyseText:
    def test_debt_scenario_legally_enforceable(self, orchestrator):
        result = orchestrator.analyse_text(
            whatsapp_text=WHATSAPP_DEBT,
            cheque_date=datetime(2024, 2, 15),
        )
        assert result.cheque_context == ChequeContext.LEGALLY_ENFORCEABLE

    def test_advance_scenario_advance_or_security(self, orchestrator):
        result = orchestrator.analyse_text(
            whatsapp_text=WHATSAPP_ADVANCE,
            cheque_date=datetime(2024, 3, 14),
        )
        assert result.cheque_context == ChequeContext.ADVANCE_OR_SECURITY

    def test_security_scenario_advance_or_security(self, orchestrator):
        result = orchestrator.analyse_text(
            whatsapp_text=WHATSAPP_SECURITY,
            cheque_date=datetime(2024, 3, 14),
        )
        assert result.cheque_context == ChequeContext.ADVANCE_OR_SECURITY

    def test_email_debt_scenario(self, orchestrator):
        result = orchestrator.analyse_text(
            email_text=EMAIL_DEBT,
            cheque_date=datetime(2024, 2, 15),
        )
        assert result.cheque_context == ChequeContext.LEGALLY_ENFORCEABLE

    def test_no_input_insufficient_data(self, orchestrator):
        result = orchestrator.analyse_text(cheque_date=datetime(2024, 2, 15))
        assert result.cheque_context == ChequeContext.INSUFFICIENT_DATA


class TestOrchestratorAnalyseFiles:
    def test_whatsapp_file_debt(self, orchestrator, tmp_path):
        f = tmp_path / "chat.txt"
        f.write_text(WHATSAPP_DEBT.strip(), encoding="utf-8")
        result = orchestrator.analyse(
            whatsapp_files=[str(f)],
            cheque_date=datetime(2024, 2, 15),
        )
        assert result.cheque_context == ChequeContext.LEGALLY_ENFORCEABLE

    def test_email_file(self, orchestrator, tmp_path):
        f = tmp_path / "email.eml"
        f.write_text(EMAIL_DEBT.strip(), encoding="utf-8")
        result = orchestrator.analyse(
            email_files=[str(f)],
            cheque_date=datetime(2024, 2, 15),
        )
        assert result.cheque_context == ChequeContext.LEGALLY_ENFORCEABLE

    def test_missing_file_returns_result(self, orchestrator):
        """A missing file should log a warning but not raise."""
        result = orchestrator.analyse(
            whatsapp_files=["/nonexistent/path.txt"],
            cheque_date=datetime(2024, 2, 15),
        )
        # Should return INSUFFICIENT_DATA since no comms were loaded
        assert result.cheque_context == ChequeContext.INSUFFICIENT_DATA


class TestOrchestratorReport:
    def test_report_returns_json_string(self, orchestrator):
        import json

        result = orchestrator.analyse_text(
            whatsapp_text=WHATSAPP_DEBT,
            cheque_date=datetime(2024, 2, 15),
        )
        report = orchestrator.report(result)
        parsed = json.loads(report)
        assert "cheque_context" in parsed
        assert "summary" in parsed
        assert "timeline" in parsed

    def test_is_legally_enforceable_property(self, orchestrator):
        result = orchestrator.analyse_text(
            whatsapp_text=WHATSAPP_DEBT,
            cheque_date=datetime(2024, 2, 15),
        )
        assert result.is_legally_enforceable is True
