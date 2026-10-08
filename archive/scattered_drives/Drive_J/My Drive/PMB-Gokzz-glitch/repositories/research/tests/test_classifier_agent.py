"""
Tests for ClassifierAgent (Agent A).
"""

import pytest

from src.agents.classifier_agent import ClassifierAgent
from src.models.communication import Communication, Intent, SourceType
from datetime import datetime


@pytest.fixture
def agent():
    return ClassifierAgent()


def make_comm(text: str) -> Communication:
    return Communication(
        text=text,
        timestamp=datetime(2024, 2, 14, 10, 0),
        sender="test",
        source_type=SourceType.WHATSAPP,
    )


class TestSecurityChequeClassification:
    def test_explicit_security_cheque(self, agent):
        comm = make_comm("I am giving you a security cheque for ₹50,000.")
        agent.classify(comm)
        assert comm.intent == Intent.SECURITY_CHEQUE
        assert comm.confidence >= 0.90

    def test_pdc_as_security(self, agent):
        comm = make_comm(
            "This PDC is held as security. Please do not encash it."
        )
        agent.classify(comm)
        assert comm.intent == Intent.SECURITY_CHEQUE

    def test_guarantee_cheque(self, agent):
        comm = make_comm("Here is the guarantee cheque for the contract.")
        agent.classify(comm)
        assert comm.intent == Intent.SECURITY_CHEQUE

    def test_do_not_deposit(self, agent):
        comm = make_comm("Please do not deposit this cheque until delivery is confirmed.")
        agent.classify(comm)
        assert comm.intent == Intent.SECURITY_CHEQUE

    def test_collateral(self, agent):
        comm = make_comm("The cheque is given as collateral for the advance.")
        agent.classify(comm)
        assert comm.intent == Intent.SECURITY_CHEQUE


class TestAdvancePaymentClassification:
    def test_advance_for_goods(self, agent):
        comm = make_comm("Here is the advance for the goods we ordered.")
        agent.classify(comm)
        assert comm.intent == Intent.ADVANCE_PAYMENT

    def test_booking_amount(self, agent):
        comm = make_comm("I am sending the booking amount of ₹1,00,000.")
        agent.classify(comm)
        assert comm.intent == Intent.ADVANCE_PAYMENT

    def test_upfront_payment(self, agent):
        comm = make_comm("Please accept this upfront payment before we begin.")
        agent.classify(comm)
        assert comm.intent == Intent.ADVANCE_PAYMENT

    def test_prepayment(self, agent):
        comm = make_comm("This is a prepayment for the services to be rendered.")
        agent.classify(comm)
        assert comm.intent == Intent.ADVANCE_PAYMENT

    def test_token_money(self, agent):
        comm = make_comm("Sending token money of Rs. 25,000 to confirm the order.")
        agent.classify(comm)
        assert comm.intent == Intent.ADVANCE_PAYMENT


class TestPreExistingDebtClassification:
    def test_invoice_payment(self, agent):
        comm = make_comm(
            "Here is the cheque for last month's invoice. "
            "Payment against Invoice No. INV-2024-0145."
        )
        agent.classify(comm)
        assert comm.intent == Intent.PRE_EXISTING_DEBT
        assert comm.confidence >= 0.90

    def test_outstanding_balance(self, agent):
        comm = make_comm("Please clear the outstanding balance of ₹2,50,000 at the earliest.")
        agent.classify(comm)
        assert comm.intent == Intent.PRE_EXISTING_DEBT

    def test_pending_dues(self, agent):
        comm = make_comm("I am attaching the cheque to settle the pending dues.")
        agent.classify(comm)
        assert comm.intent == Intent.PRE_EXISTING_DEBT

    def test_previous_month_invoice(self, agent):
        comm = make_comm("This is the payment for the previous month's work.")
        agent.classify(comm)
        assert comm.intent == Intent.PRE_EXISTING_DEBT

    def test_clearing_account(self, agent):
        comm = make_comm("The cheque is for clearing the dues on your account.")
        agent.classify(comm)
        assert comm.intent == Intent.PRE_EXISTING_DEBT


class TestRepaymentClassification:
    def test_repayment_loan(self, agent):
        comm = make_comm("I am sending this cheque for repayment of the loan.")
        agent.classify(comm)
        assert comm.intent == Intent.REPAYMENT

    def test_settle_loan(self, agent):
        comm = make_comm("Please use this to settle the loan outstanding.")
        agent.classify(comm)
        assert comm.intent == Intent.REPAYMENT

    def test_paying_back(self, agent):
        comm = make_comm("I am paying back the ₹5 lakh I borrowed last year.")
        agent.classify(comm)
        assert comm.intent == Intent.REPAYMENT

    def test_emi(self, agent):
        comm = make_comm("Here is the EMI cheque for this month.")
        agent.classify(comm)
        assert comm.intent == Intent.REPAYMENT


class TestNeutralClassification:
    def test_generic_message(self, agent):
        comm = make_comm("Hello, how are you doing?")
        agent.classify(comm)
        assert comm.intent == Intent.NEUTRAL
        assert comm.confidence == 0.0

    def test_meeting_message(self, agent):
        comm = make_comm("Let us meet tomorrow at 3 PM.")
        agent.classify(comm)
        assert comm.intent == Intent.NEUTRAL


class TestClassifyAll:
    def test_classify_all_list(self, agent):
        comms = [
            make_comm("Advance payment for goods"),
            make_comm("Payment against Invoice INV-001"),
            make_comm("Security cheque for the contract"),
        ]
        result = agent.classify_all(comms)
        assert len(result) == 3
        assert result[0].intent == Intent.ADVANCE_PAYMENT
        assert result[1].intent == Intent.PRE_EXISTING_DEBT
        assert result[2].intent == Intent.SECURITY_CHEQUE

    def test_classify_all_returns_same_list(self, agent):
        comms = [make_comm("Some text")]
        result = agent.classify_all(comms)
        assert result is comms


class TestExplain:
    def test_explain_returns_dict(self, agent):
        result = agent.explain("Here is the advance for the booking amount.")
        assert isinstance(result, dict)
        assert Intent.ADVANCE_PAYMENT.value in result

    def test_explain_empty_for_neutral(self, agent):
        result = agent.explain("Good morning!")
        assert result == {}


class TestSecurityOverridesAdvance:
    """Security-cheque intent should beat advance-payment intent."""

    def test_security_beats_advance(self, agent):
        comm = make_comm(
            "Here is the advance payment. Please keep this as a security cheque."
        )
        agent.classify(comm)
        # Security cheque has higher priority in the _INTENT_MAP
        assert comm.intent == Intent.SECURITY_CHEQUE
