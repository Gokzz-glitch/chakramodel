"""
Tests for ChronologistAgent (Agent B).
"""

import pytest
from datetime import datetime

from src.agents.chronologist_agent import ChronologistAgent
from src.models.communication import (
    Communication,
    ChequeContext,
    Intent,
    SourceType,
    TimelineEntry,
)


@pytest.fixture
def agent():
    return ChronologistAgent(min_confidence=0.60)


def make_classified(
    text: str,
    intent: Intent,
    confidence: float,
    timestamp: datetime,
    sender: str = "test",
) -> Communication:
    comm = Communication(
        text=text,
        timestamp=timestamp,
        sender=sender,
        source_type=SourceType.WHATSAPP,
        intent=intent,
        confidence=confidence,
    )
    return comm


# Reference dates
CHEQUE_DATE = datetime(2024, 2, 15)
PRE_DATE = datetime(2024, 2, 10)  # 5 days before cheque
POST_DATE = datetime(2024, 2, 20)  # 5 days after cheque


class TestInsufficientData:
    def test_empty_list(self, agent):
        result = agent.build_timeline([], cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.INSUFFICIENT_DATA

    def test_all_low_confidence(self, agent):
        comms = [
            make_classified("some text", Intent.PRE_EXISTING_DEBT, 0.30, PRE_DATE),
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.INSUFFICIENT_DATA

    def test_only_neutral_intent(self, agent):
        comms = [
            make_classified("Hello", Intent.NEUTRAL, 0.0, PRE_DATE),
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.INSUFFICIENT_DATA


class TestLegallyEnforceable:
    def test_pre_existing_debt_before_cheque(self, agent):
        comms = [
            make_classified(
                "Payment against Invoice INV-001",
                Intent.PRE_EXISTING_DEBT,
                0.95,
                PRE_DATE,
            )
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.LEGALLY_ENFORCEABLE
        assert result.is_legally_enforceable

    def test_repayment_before_cheque(self, agent):
        comms = [
            make_classified(
                "Repayment of the loan taken last year",
                Intent.REPAYMENT,
                0.90,
                PRE_DATE,
            )
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.LEGALLY_ENFORCEABLE

    def test_multiple_supporting_comms(self, agent):
        comms = [
            make_classified(
                "Invoice INV-001 outstanding",
                Intent.PRE_EXISTING_DEBT,
                0.90,
                datetime(2024, 2, 5),
            ),
            make_classified(
                "Still pending dues",
                Intent.ACKNOWLEDGEMENT,
                0.75,
                datetime(2024, 2, 8),
            ),
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.LEGALLY_ENFORCEABLE
        assert len(result.supporting_entries) >= 1

    def test_summary_mentions_supporting_count(self, agent):
        comms = [
            make_classified(
                "Payment against Invoice",
                Intent.PRE_EXISTING_DEBT,
                0.90,
                PRE_DATE,
            )
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert "1" in result.summary


class TestAdvanceOrSecurity:
    def test_security_cheque_any_position(self, agent):
        comms = [
            make_classified(
                "This is a security cheque",
                Intent.SECURITY_CHEQUE,
                0.95,
                PRE_DATE,
            )
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.ADVANCE_OR_SECURITY

    def test_advance_only_before_cheque(self, agent):
        comms = [
            make_classified(
                "Advance payment for goods before delivery",
                Intent.ADVANCE_PAYMENT,
                0.90,
                PRE_DATE,
            )
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.ADVANCE_OR_SECURITY

    def test_security_overrides_debt(self, agent):
        """Even when debt signals exist, a security signal is decisive."""
        comms = [
            make_classified(
                "Security cheque",
                Intent.SECURITY_CHEQUE,
                0.95,
                PRE_DATE,
            ),
            make_classified(
                "Outstanding invoice",
                Intent.PRE_EXISTING_DEBT,
                0.90,
                PRE_DATE,
            ),
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.ADVANCE_OR_SECURITY


class TestAmbiguous:
    def test_conflicting_signals(self, agent):
        comms = [
            make_classified(
                "Advance for the order",
                Intent.ADVANCE_PAYMENT,
                0.90,
                PRE_DATE,
            ),
            make_classified(
                "Payment against Invoice",
                Intent.PRE_EXISTING_DEBT,
                0.90,
                PRE_DATE,
            ),
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.AMBIGUOUS

    def test_debt_signals_only_after_cheque(self, agent):
        comms = [
            make_classified(
                "Outstanding dues on Invoice",
                Intent.PRE_EXISTING_DEBT,
                0.90,
                POST_DATE,  # after cheque date
            )
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.cheque_context == ChequeContext.AMBIGUOUS


class TestTimelineConstruction:
    def test_timeline_sorted_chronologically(self, agent):
        comms = [
            make_classified("Later message", Intent.PRE_EXISTING_DEBT, 0.90, POST_DATE),
            make_classified("Earlier message", Intent.PRE_EXISTING_DEBT, 0.90, PRE_DATE),
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        timestamps = [e.timestamp for e in result.timeline]
        assert timestamps == sorted(timestamps)

    def test_days_before_cheque_calculated(self, agent):
        comms = [
            make_classified("Invoice outstanding", Intent.PRE_EXISTING_DEBT, 0.90, PRE_DATE)
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.timeline[0].days_before_cheque == 5  # CHEQUE_DATE - PRE_DATE

    def test_days_negative_for_post_cheque(self, agent):
        comms = [
            make_classified("Message after cheque", Intent.PRE_EXISTING_DEBT, 0.90, POST_DATE)
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.timeline[0].days_before_cheque == -5

    def test_no_cheque_date_none_offset(self, agent):
        comms = [
            make_classified("Invoice outstanding", Intent.PRE_EXISTING_DEBT, 0.90, PRE_DATE)
        ]
        result = agent.build_timeline(comms, cheque_date=None)
        # Without cheque_date, days_before_cheque should be None
        assert result.timeline[0].days_before_cheque is None

    def test_pivotal_flag_set_for_high_confidence(self, agent):
        comms = [
            make_classified("Invoice outstanding", Intent.PRE_EXISTING_DEBT, 0.90, PRE_DATE)
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.timeline[0].is_pivotal is True

    def test_pivotal_flag_false_for_low_confidence(self, agent):
        comms = [
            make_classified("Invoice outstanding", Intent.PRE_EXISTING_DEBT, 0.30, PRE_DATE)
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        assert result.timeline[0].is_pivotal is False


class TestToDict:
    def test_to_dict_has_required_keys(self, agent):
        comms = [
            make_classified("Invoice outstanding", Intent.PRE_EXISTING_DEBT, 0.90, PRE_DATE)
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        d = result.to_dict()
        assert "cheque_context" in d
        assert "summary" in d
        assert "timeline" in d
        assert "cheque_date" in d

    def test_to_dict_cheque_date_iso_format(self, agent):
        comms = [
            make_classified("Invoice outstanding", Intent.PRE_EXISTING_DEBT, 0.90, PRE_DATE)
        ]
        result = agent.build_timeline(comms, cheque_date=CHEQUE_DATE)
        d = result.to_dict()
        assert "2024-02-15" in d["cheque_date"]

    def test_to_dict_no_cheque_date(self, agent):
        comms = [
            make_classified("Invoice outstanding", Intent.PRE_EXISTING_DEBT, 0.90, PRE_DATE)
        ]
        result = agent.build_timeline(comms, cheque_date=None)
        d = result.to_dict()
        assert d["cheque_date"] is None
