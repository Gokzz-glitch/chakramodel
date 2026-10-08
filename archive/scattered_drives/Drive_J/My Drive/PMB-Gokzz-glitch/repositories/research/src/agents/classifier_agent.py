"""
Agent A – The Classifier
========================
Scans each :class:`Communication` and assigns an :class:`Intent` label based
on the message text.

Classification strategy
-----------------------
The classifier uses a **multi-tier rule-based approach** that mirrors the
judicial tests applied by Indian courts when evaluating Section 138 NI Act
cases:

1. **Security-cheque patterns** – explicit mentions of "security",
   "guarantee", "collateral", or "post-dated cheque as security".
2. **Advance-payment patterns** – language suggesting payment *before* goods /
   services are delivered ("advance", "upfront", "deposit", "booking amount").
3. **Pre-existing debt patterns** – references to invoices, bills, dues,
   outstanding balances, or phrases like "payment against Invoice No. …".
4. **Repayment patterns** – explicit repayment language ("repay", "returning
   the amount", "settle the loan").
5. **Acknowledgement patterns** – acknowledgement of a balance or liability
   without an explicit payment direction.
6. **Neutral / Unknown** – no strong signal detected.

Each pattern set carries a **weight** so that when multiple signals fire the
classifier selects the highest-confidence intent.

Extensibility
-------------
The rule sets are exposed as class attributes so they can be overridden or
extended without subclassing::

    agent = ClassifierAgent()
    agent.PRE_EXISTING_DEBT_PATTERNS.append(re.compile(r"debit note", re.I))
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from src.models.communication import Communication, Intent


# ---------------------------------------------------------------------------
# Pattern definitions
# (pattern, weight)  –  higher weight wins when multiple patterns match
# ---------------------------------------------------------------------------

_PatternList = List[Tuple[re.Pattern, float]]


def _compile(patterns: List[Tuple[str, float]]) -> _PatternList:
    return [(re.compile(p, re.IGNORECASE), w) for p, w in patterns]


_SECURITY_RAW: List[Tuple[str, float]] = [
    (r"\bsecurity\s+cheque\b", 0.95),
    (r"\bpost[- ]?dated\s+cheque\s+as\s+security\b", 0.95),
    (r"\bcheque\s+as\s+(?:a\s+)?(?:security|guarantee|collateral)\b", 0.95),
    (r"\bgiven\s+as\s+(?:a\s+)?(?:security|guarantee|collateral)\b", 0.90),
    (r"\bheld\s+as\s+(?:a\s+)?security\b", 0.90),
    (r"\bcollateral\b", 0.75),
    (r"\bguarantee\s+cheque\b", 0.85),
    (r"\bPDC\b", 0.70),          # Post-Dated Cheque (common abbreviation)
    (r"\bdo\s+not\s+(?:encash|deposit|present)\b", 0.70),
]

_ADVANCE_RAW: List[Tuple[str, float]] = [
    (r"\badvance\s+(?:payment|amount|for\b)", 0.90),
    (r"\bpaying\s+(?:in\s+)?advance\b", 0.90),
    (r"\badvance\b", 0.65),
    (r"\bupfront\s+payment\b", 0.85),
    (r"\bdeposit\s+(?:for|towards|of)\b", 0.80),
    (r"\bbooking\s+amount\b", 0.85),
    (r"\btoken\s+(?:money|amount)\b", 0.80),
    (r"\bbefore\s+(?:delivery|dispatch|shipment|supply)\b", 0.75),
    (r"\bprepayment\b", 0.85),
    (r"\bdown\s+payment\b", 0.80),
]

_PRE_EXISTING_DEBT_RAW: List[Tuple[str, float]] = [
    (r"\bpayment\s+against\s+(?:invoice|bill|order)\b", 0.95),
    (r"\b(?:invoice|inv\.?)\s+(?:no\.?|number|#)\s*\S+", 0.90),
    (r"\b(?:bill|bills)\s+(?:no\.?|number|#)\s*\S+", 0.85),
    (r"\boutstanding\s+(?:amount|balance|dues|payment)\b", 0.90),
    (r"\bpending\s+(?:dues|balance|invoice|payment)\b", 0.85),
    (r"\bpayment\s+(?:of|for)\s+(?:the\s+)?(?:last|previous|prior)\s+\w+\b", 0.90),
    (r"\bpast\s+(?:dues|invoices|bills)\b", 0.85),
    (r"\bsettle(?:ment)?\s+(?:of\s+)?(?:dues|outstanding|account)\b", 0.85),
    (r"\bdue\s+(?:amount|balance)\b", 0.80),
    (r"\bbalance\s+(?:due|payable|outstanding)\b", 0.80),
    (r"\bclearing\s+(?:the\s+)?(?:dues|balance|account)\b", 0.85),
    (r"\bcheque\s+(?:for|towards)\s+(?:last|previous)\s+\w+(?:'s)?\s+(?:invoice|bill)\b", 0.95),
    (r"\bowed\b|\bowe\b|\bowes\b", 0.70),
    (r"\bcredit\s+(?:note|period)\b", 0.75),
    (r"\brecovery\s+of\s+(?:amount|dues|payment)\b", 0.85),
]

_REPAYMENT_RAW: List[Tuple[str, float]] = [
    (r"\brepay(?:ment|ing)?\b", 0.90),
    (r"\breturn(?:ing)?\s+(?:the\s+)?(?:amount|money|loan|funds)\b", 0.90),
    (r"\brefund(?:ing)?\b", 0.75),
    (r"\bsettle\s+(?:the\s+)?loan\b", 0.90),
    (r"\bpaying\s+back\b", 0.85),
    (r"\bpayment\s+of\s+(?:loan|debt|borrowing)\b", 0.90),
    (r"\breimburse(?:ment)?\b", 0.75),
    (r"\bEMI\b", 0.80),
]

_ACKNOWLEDGEMENT_RAW: List[Tuple[str, float]] = [
    (r"\backnowledge(?:ment)?\s+of\s+(?:receipt|payment|amount)\b", 0.85),
    (r"\bconfirm(?:ing)?\s+(?:receipt|payment|balance)\b", 0.80),
    (r"\breceipt\s+of\s+(?:the\s+)?(?:amount|payment|cheque)\b", 0.80),
    (r"\bremind(?:er|ing)?\s+(?:for\s+)?(?:payment|dues|balance)\b", 0.75),
    (r"\bfollowing\s+up\s+(?:on|for)\s+(?:payment|dues)\b", 0.75),
    (r"\bstill\s+(?:pending|outstanding|unpaid)\b", 0.70),
]


class ClassifierAgent:
    """
    Agent A – classifies the payment intent of each :class:`Communication`.

    Usage
    -----
    ::

        agent = ClassifierAgent()
        classified = agent.classify_all(communications)
        for comm in classified:
            print(comm.intent, comm.confidence, comm.text[:60])
    """

    SECURITY_PATTERNS: _PatternList = _compile(_SECURITY_RAW)
    ADVANCE_PATTERNS: _PatternList = _compile(_ADVANCE_RAW)
    PRE_EXISTING_DEBT_PATTERNS: _PatternList = _compile(_PRE_EXISTING_DEBT_RAW)
    REPAYMENT_PATTERNS: _PatternList = _compile(_REPAYMENT_RAW)
    ACKNOWLEDGEMENT_PATTERNS: _PatternList = _compile(_ACKNOWLEDGEMENT_RAW)

    # Ordered by legal priority (highest first):
    # security and advance patterns can *defeat* a Section 138 complaint, so
    # they take precedence over pro-complainant signals.
    _INTENT_MAP: List[Tuple[Intent, "_PatternList"]] = [
        (Intent.SECURITY_CHEQUE, SECURITY_PATTERNS),
        (Intent.ADVANCE_PAYMENT, ADVANCE_PATTERNS),
        (Intent.PRE_EXISTING_DEBT, PRE_EXISTING_DEBT_PATTERNS),
        (Intent.REPAYMENT, REPAYMENT_PATTERNS),
        (Intent.ACKNOWLEDGEMENT, ACKNOWLEDGEMENT_PATTERNS),
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, communication: Communication) -> Communication:
        """
        Classify a single :class:`Communication` in-place and return it.

        Sets ``communication.intent`` and ``communication.confidence``.
        """
        intent, confidence = self._infer(communication.text)
        communication.intent = intent
        communication.confidence = confidence
        return communication

    def classify_all(
        self, communications: List[Communication]
    ) -> List[Communication]:
        """Classify every item in *communications* in-place and return the list."""
        for comm in communications:
            self.classify(comm)
        return communications

    # ------------------------------------------------------------------
    # Internal logic
    # ------------------------------------------------------------------

    def _infer(self, text: str) -> Tuple[Intent, float]:
        """
        Scan *text* against all pattern sets and return the best
        ``(Intent, confidence)`` pair.

        When multiple intents share the same best confidence the one listed
        earlier in ``_INTENT_MAP`` wins (security > advance > debt …).
        """
        best_intent: Intent = Intent.NEUTRAL
        best_confidence: float = 0.0

        scores: Dict[Intent, float] = {}

        for intent, patterns in self._INTENT_MAP:
            score = self._score(text, patterns)
            if score > 0:
                scores[intent] = score

        if not scores:
            return Intent.NEUTRAL, 0.0

        # Pick the intent with the maximum score; ties broken by _INTENT_MAP order
        for intent, _ in self._INTENT_MAP:
            if intent in scores:
                score = scores[intent]
                if score > best_confidence:
                    best_confidence = score
                    best_intent = intent

        # Cap confidence at 0.99
        return best_intent, min(best_confidence, 0.99)

    @staticmethod
    def _score(text: str, patterns: _PatternList) -> float:
        """
        Return the **maximum** weight of any pattern that matches *text*.

        Using the maximum (rather than sum) prevents long messages from
        artificially inflating confidence just because they repeat keywords.
        """
        best = 0.0
        for pattern, weight in patterns:
            if pattern.search(text):
                best = max(best, weight)
        return best

    # ------------------------------------------------------------------
    # Diagnostic helper
    # ------------------------------------------------------------------

    def explain(self, text: str) -> Dict[str, float]:
        """
        Return a mapping of ``intent → best_matched_weight`` for *all* intents
        that have at least one pattern match.  Useful for debugging.
        """
        result: Dict[str, float] = {}
        for intent, patterns in self._INTENT_MAP:
            score = self._score(text, patterns)
            if score > 0:
                result[intent.value] = score
        return result
