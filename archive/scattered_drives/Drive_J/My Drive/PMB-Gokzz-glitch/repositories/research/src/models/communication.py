"""
Data models for the Temporal NLP Debt Verification system.

These models represent parsed communications, inferred intents, timeline
entries, and the final analysis result for Section 138 NI Act cases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class SourceType(str, Enum):
    """Origin of a parsed communication."""

    WHATSAPP = "whatsapp"
    EMAIL = "email"
    PDF = "pdf"
    UNKNOWN = "unknown"


class Intent(str, Enum):
    """
    Business intent inferred from a communication.

    ADVANCE_PAYMENT    – cheque / payment issued *before* goods or services are
                         delivered (no pre-existing liability).
    PRE_EXISTING_DEBT  – cheque issued to discharge an already-crystallised debt
                         (supports a valid Section 138 complaint).
    SECURITY_CHEQUE    – cheque given as collateral / guarantee, not for payment.
    REPAYMENT          – explicit mention of repaying an earlier amount.
    ACKNOWLEDGEMENT    – acknowledgement of an outstanding balance or invoice.
    NEUTRAL            – no clear financial intent detected.
    UNKNOWN            – cannot be classified from the available text.
    """

    ADVANCE_PAYMENT = "advance_payment"
    PRE_EXISTING_DEBT = "pre_existing_debt"
    SECURITY_CHEQUE = "security_cheque"
    REPAYMENT = "repayment"
    ACKNOWLEDGEMENT = "acknowledgement"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class ChequeContext(str, Enum):
    """
    High-level legal conclusion produced by the Chronologist agent.

    LEGALLY_ENFORCEABLE – strong evidence the cheque discharged a pre-existing
                          debt, supporting a Section 138 complaint.
    ADVANCE_OR_SECURITY – evidence suggests the cheque was advance / security,
                          which typically defeats a Section 138 complaint.
    INSUFFICIENT_DATA   – not enough information to draw a conclusion.
    AMBIGUOUS           – conflicting signals; manual review recommended.
    """

    LEGALLY_ENFORCEABLE = "legally_enforceable"
    ADVANCE_OR_SECURITY = "advance_or_security"
    INSUFFICIENT_DATA = "insufficient_data"
    AMBIGUOUS = "ambiguous"


@dataclass
class Communication:
    """
    A single parsed message from any supported source.

    Attributes
    ----------
    text:        Raw / cleaned message body.
    timestamp:   When the message was sent (UTC-aware or naive datetime).
    sender:      Identifier of the sender (phone number, email address, etc.).
    source_type: Where the message came from (WhatsApp, Email, PDF …).
    intent:      Inferred intent; populated by ClassifierAgent.
    confidence:  Classifier confidence in [0, 1]; populated by ClassifierAgent.
    metadata:    Arbitrary extra key-value pairs from the parser.
    """

    text: str
    timestamp: datetime
    sender: str = ""
    source_type: SourceType = SourceType.UNKNOWN
    intent: Intent = Intent.UNKNOWN
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def date(self) -> Optional[datetime.date]:
        """Return just the date part of the timestamp (or None)."""
        return self.timestamp.date() if self.timestamp else None

    def has_monetary_amount(self) -> bool:
        """Return True if the text mentions a monetary amount."""
        pattern = (
            r"(?:₹|Rs\.?|INR|USD|\$)\s?\d[\d,]*(?:\.\d{1,2})?"
            r"|\d[\d,]*(?:\.\d{1,2})?\s?(?:rupees?|lakh|lakhs|crore|crores)"
        )
        return bool(re.search(pattern, self.text, re.IGNORECASE))

    def has_cheque_reference(self) -> bool:
        """Return True if the text directly references a cheque."""
        keywords = r"\bcheque\b|\bcheck\b|\bchq\b|\bcheque\s+no\b|\bcheque\s+number\b"
        return bool(re.search(keywords, self.text, re.IGNORECASE))

    def __repr__(self) -> str:
        ts = self.timestamp.isoformat() if self.timestamp else "N/A"
        return (
            f"Communication(sender={self.sender!r}, ts={ts}, "
            f"intent={self.intent.value}, text={self.text[:60]!r})"
        )


@dataclass
class TimelineEntry:
    """
    A decorated Communication anchored on the business timeline.

    Attributes
    ----------
    communication:   The underlying parsed message.
    days_before_cheque: Number of days *before* the cheque date
                        (negative means the communication came *after*).
    is_pivotal:      True if this entry materially affects the legal analysis.
    legal_note:      Human-readable annotation explaining the legal significance.
    """

    communication: Communication
    days_before_cheque: Optional[int] = None
    is_pivotal: bool = False
    legal_note: str = ""

    @property
    def timestamp(self) -> datetime:
        return self.communication.timestamp

    @property
    def intent(self) -> Intent:
        return self.communication.intent

    def __repr__(self) -> str:
        rel = (
            f"{self.days_before_cheque}d before cheque"
            if self.days_before_cheque is not None
            else "unknown offset"
        )
        return (
            f"TimelineEntry(intent={self.intent.value}, {rel}, "
            f"pivotal={self.is_pivotal})"
        )


@dataclass
class AnalysisResult:
    """
    Final output produced by the Orchestrator.

    Attributes
    ----------
    cheque_context:       High-level legal conclusion.
    cheque_date:          Date written on the cheque (if provided).
    timeline:             Ordered list of TimelineEntry objects.
    summary:              Human-readable summary of the analysis.
    classifier_version:   Version / identifier of the classifier model used.
    supporting_entries:   Subset of timeline entries that support the conclusion.
    conflicting_entries:  Subset that conflict with the conclusion.
    """

    cheque_context: ChequeContext = ChequeContext.INSUFFICIENT_DATA
    cheque_date: Optional[datetime] = None
    timeline: List[TimelineEntry] = field(default_factory=list)
    summary: str = ""
    classifier_version: str = "rule_based_v1"
    supporting_entries: List[TimelineEntry] = field(default_factory=list)
    conflicting_entries: List[TimelineEntry] = field(default_factory=list)

    @property
    def is_legally_enforceable(self) -> bool:
        return self.cheque_context == ChequeContext.LEGALLY_ENFORCEABLE

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary (JSON-friendly)."""
        return {
            "cheque_context": self.cheque_context.value,
            "cheque_date": (
                self.cheque_date.isoformat() if self.cheque_date else None
            ),
            "summary": self.summary,
            "classifier_version": self.classifier_version,
            "timeline": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "sender": e.communication.sender,
                    "intent": e.intent.value,
                    "confidence": e.communication.confidence,
                    "days_before_cheque": e.days_before_cheque,
                    "is_pivotal": e.is_pivotal,
                    "legal_note": e.legal_note,
                    "text_snippet": e.communication.text[:120],
                }
                for e in self.timeline
            ],
            "supporting_count": len(self.supporting_entries),
            "conflicting_count": len(self.conflicting_entries),
        }
