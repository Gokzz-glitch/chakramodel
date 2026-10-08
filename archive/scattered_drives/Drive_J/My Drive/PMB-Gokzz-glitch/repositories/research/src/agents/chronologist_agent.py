"""
Agent B – The Chronologist
==========================
Constructs a temporal timeline of business communications relative to the
cheque date and produces a :class:`ChequeContext` conclusion.

Legal reasoning model
---------------------
The Negotiable Instruments Act, 1881 (Section 138) requires the cheque to be
issued for the *discharge of a legally enforceable debt or liability*.  The
chronological relationship between the parties' communications and the cheque
date is a key piece of evidence:

* **Pre-cheque PRE_EXISTING_DEBT / REPAYMENT signals** → strong indication
  that the debt existed before the cheque was drawn → supports complainant.
* **Pre-cheque ADVANCE_PAYMENT signals** → the payment preceded delivery →
  no pre-existing debt at the time of the cheque → defeats complainant.
* **Pre-cheque SECURITY_CHEQUE signals** → explicit collateral arrangement →
  cheque was not for discharge of a debt → defeats complainant.
* **Post-cheque signals** → less probative but still considered for context.
* **No cheque date provided** → analysis is performed on the absolute
  timeline without anchoring to any specific date.

Decision rules (applied in order)
----------------------------------
1. If ``SECURITY_CHEQUE`` signals appear anywhere in the timeline → 
   **ADVANCE_OR_SECURITY**.
2. If ``ADVANCE_PAYMENT`` signals appear *before* the cheque date with no
   counteracting ``PRE_EXISTING_DEBT`` or ``REPAYMENT`` signals →
   **ADVANCE_OR_SECURITY**.
3. If ``PRE_EXISTING_DEBT`` or ``REPAYMENT`` signals appear *before* the
   cheque date → **LEGALLY_ENFORCEABLE**.
4. If ``PRE_EXISTING_DEBT`` signals appear *after* the cheque date only →
   **AMBIGUOUS** (could be back-dated documentation).
5. Conflicting pre-cheque signals (advance *and* debt) → **AMBIGUOUS**.
6. Fewer than ``MIN_COMMUNICATIONS`` classified messages → 
   **INSUFFICIENT_DATA**.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from src.models.communication import (
    AnalysisResult,
    ChequeContext,
    Communication,
    Intent,
    TimelineEntry,
)

# Minimum number of classified communications required to draw any conclusion.
MIN_COMMUNICATIONS = 1

# Intents that *support* a legally enforceable debt finding
_SUPPORTING_INTENTS = {Intent.PRE_EXISTING_DEBT, Intent.REPAYMENT, Intent.ACKNOWLEDGEMENT}

# Intents that *contradict* a legally enforceable debt finding
_DEFEATING_INTENTS = {Intent.SECURITY_CHEQUE, Intent.ADVANCE_PAYMENT}


class ChronologistAgent:
    """
    Agent B – builds a timeline and infers the :class:`ChequeContext`.

    Parameters
    ----------
    min_confidence :
        Minimum classifier confidence required for a :class:`Communication`
        to be considered when drawing conclusions. Messages below this
        threshold are included in the timeline but marked non-pivotal.
    """

    def __init__(self, min_confidence: float = 0.60) -> None:
        self.min_confidence = min_confidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_timeline(
        self,
        communications: List[Communication],
        cheque_date: Optional[datetime] = None,
    ) -> AnalysisResult:
        """
        Build a :class:`AnalysisResult` from a list of classified
        :class:`Communication` objects.

        Parameters
        ----------
        communications :
            Communications already classified by :class:`ClassifierAgent`.
        cheque_date :
            The date written on the cheque.  If *None*, relative dating is
            skipped but the timeline is still constructed.
        """
        if not communications:
            return AnalysisResult(
                cheque_context=ChequeContext.INSUFFICIENT_DATA,
                cheque_date=cheque_date,
                summary="No communications were provided for analysis.",
            )

        # Sort chronologically (normalise timestamps to avoid tz-aware/naive issues)
        sorted_comms = sorted(
            communications, key=lambda c: self._as_naive(c.timestamp)
        )

        # Build raw timeline entries
        timeline: List[TimelineEntry] = [
            self._make_entry(comm, cheque_date) for comm in sorted_comms
        ]

        # Separate high-confidence entries
        pivotal = [e for e in timeline if e.is_pivotal]

        if len(pivotal) < MIN_COMMUNICATIONS:
            return AnalysisResult(
                cheque_context=ChequeContext.INSUFFICIENT_DATA,
                cheque_date=cheque_date,
                timeline=timeline,
                summary=(
                    "Insufficient high-confidence signals to draw a legal conclusion. "
                    f"Only {len(pivotal)} communication(s) exceeded the confidence "
                    f"threshold of {self.min_confidence:.0%}."
                ),
            )

        context, supporting, conflicting, summary = self._decide(
            pivotal, cheque_date
        )

        return AnalysisResult(
            cheque_context=context,
            cheque_date=cheque_date,
            timeline=timeline,
            summary=summary,
            supporting_entries=supporting,
            conflicting_entries=conflicting,
        )

    # ------------------------------------------------------------------
    # Entry construction
    # ------------------------------------------------------------------

    def _make_entry(
        self, comm: Communication, cheque_date: Optional[datetime]
    ) -> TimelineEntry:
        days_before: Optional[int] = None
        legal_note = ""

        if cheque_date is not None:
            # Normalise both datetimes to naive (UTC) to avoid tz-aware /
            # tz-naive comparison errors when emails carry timezone offsets.
            comm_ts = self._as_naive(comm.timestamp)
            cheque_naive = self._as_naive(cheque_date)
            delta = (cheque_naive - comm_ts).days
            days_before = delta  # positive → before cheque; negative → after

        is_pivotal = (
            comm.intent not in {Intent.NEUTRAL, Intent.UNKNOWN}
            and comm.confidence >= self.min_confidence
        )

        if is_pivotal:
            legal_note = self._legal_annotation(comm.intent, days_before)

        return TimelineEntry(
            communication=comm,
            days_before_cheque=days_before,
            is_pivotal=is_pivotal,
            legal_note=legal_note,
        )

    @staticmethod
    def _as_naive(dt: datetime) -> datetime:
        """Strip timezone information from a datetime, converting to UTC first."""
        if dt.tzinfo is not None:
            from datetime import timezone
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    @staticmethod
    def _legal_annotation(intent: Intent, days_before: Optional[int]) -> str:
        """Produce a short legal annotation for a pivotal entry."""
        timing = ""
        if days_before is not None:
            if days_before > 0:
                timing = f" ({days_before} day(s) before the cheque date)"
            elif days_before == 0:
                timing = " (on the same day as the cheque date)"
            else:
                timing = f" ({abs(days_before)} day(s) after the cheque date)"

        notes = {
            Intent.PRE_EXISTING_DEBT: (
                f"Indicates a pre-existing debt or outstanding invoice{timing}. "
                "Supports the complainant's Section 138 claim."
            ),
            Intent.REPAYMENT: (
                f"Repayment language detected{timing}. "
                "Suggests the cheque discharged an earlier liability."
            ),
            Intent.ACKNOWLEDGEMENT: (
                f"Debt acknowledgement detected{timing}. "
                "Supports the existence of a prior liability."
            ),
            Intent.ADVANCE_PAYMENT: (
                f"Advance-payment language detected{timing}. "
                "May indicate cheque was issued before goods/services were delivered, "
                "potentially defeating the Section 138 complaint."
            ),
            Intent.SECURITY_CHEQUE: (
                f"Security-cheque language detected{timing}. "
                "Strongly suggests the cheque was given as collateral, "
                "which defeats a Section 138 complaint."
            ),
        }
        return notes.get(intent, "")

    # ------------------------------------------------------------------
    # Decision logic
    # ------------------------------------------------------------------

    def _decide(
        self,
        pivotal: List[TimelineEntry],
        cheque_date: Optional[datetime],
    ) -> Tuple[ChequeContext, List[TimelineEntry], List[TimelineEntry], str]:
        """
        Apply the legal decision rules and return
        ``(ChequeContext, supporting_entries, conflicting_entries, summary)``.
        """
        # Partition by temporal position relative to cheque date
        pre_cheque = [
            e for e in pivotal
            if cheque_date is None or (e.days_before_cheque is not None and e.days_before_cheque >= 0)
        ]
        post_cheque = [
            e for e in pivotal
            if cheque_date is not None and e.days_before_cheque is not None and e.days_before_cheque < 0
        ]

        supporting = [e for e in pivotal if e.intent in _SUPPORTING_INTENTS]
        defeating = [e for e in pivotal if e.intent in _DEFEATING_INTENTS]

        has_security = any(e.intent == Intent.SECURITY_CHEQUE for e in pivotal)
        has_advance_pre = any(
            e.intent == Intent.ADVANCE_PAYMENT for e in pre_cheque
        )
        has_debt_pre = any(
            e.intent in {Intent.PRE_EXISTING_DEBT, Intent.REPAYMENT}
            for e in pre_cheque
        )
        has_debt_post_only = (
            not has_debt_pre
            and any(e.intent in _SUPPORTING_INTENTS for e in post_cheque)
        )

        # ---- Rule 1: Any security-cheque signal is decisive ----
        if has_security:
            return (
                ChequeContext.ADVANCE_OR_SECURITY,
                [],
                defeating,
                self._summary_security(defeating),
            )

        # ---- Rule 2: Advance without debt ----
        if has_advance_pre and not has_debt_pre:
            return (
                ChequeContext.ADVANCE_OR_SECURITY,
                [],
                defeating,
                self._summary_advance(defeating),
            )

        # ---- Rule 3: Confirmed pre-existing debt ----
        if has_debt_pre and not has_advance_pre:
            return (
                ChequeContext.LEGALLY_ENFORCEABLE,
                supporting,
                [],
                self._summary_debt(supporting, cheque_date),
            )

        # ---- Rule 4: Debt signals only post-cheque ----
        if has_debt_post_only:
            return (
                ChequeContext.AMBIGUOUS,
                supporting,
                [],
                (
                    "Debt-related communications were found only *after* the cheque "
                    "date. This may indicate back-dated documentation; manual review "
                    "is strongly recommended."
                ),
            )

        # ---- Rule 5: Conflicting pre-cheque signals ----
        if has_debt_pre and has_advance_pre:
            return (
                ChequeContext.AMBIGUOUS,
                supporting,
                defeating,
                (
                    "Both advance-payment and pre-existing debt signals were detected "
                    "before the cheque date. The communications present contradictory "
                    "evidence; the matter should be reviewed by a legal expert."
                ),
            )

        # ---- Rule 6: Fallback ----
        return (
            ChequeContext.INSUFFICIENT_DATA,
            [],
            [],
            "The available communications do not provide sufficient evidence to "
            "determine the legal context of the cheque.",
        )

    # ------------------------------------------------------------------
    # Summary builders
    # ------------------------------------------------------------------

    @staticmethod
    def _summary_security(defeating: List[TimelineEntry]) -> str:
        count = len(defeating)
        return (
            f"Security-cheque language was detected in {count} communication(s). "
            "Under established Supreme Court jurisprudence, a cheque given as "
            "security does not meet the 'legally enforceable debt' threshold "
            "required by Section 138 NI Act. The complaint is likely to fail."
        )

    @staticmethod
    def _summary_advance(defeating: List[TimelineEntry]) -> str:
        count = len(defeating)
        return (
            f"Advance-payment language was detected in {count} communication(s) "
            "prior to the cheque date, with no evidence of a pre-existing debt. "
            "The cheque appears to have been issued before goods or services were "
            "delivered. Section 138 requires a pre-existing liability; this case "
            "may not satisfy that requirement."
        )

    @staticmethod
    def _summary_debt(
        supporting: List[TimelineEntry], cheque_date: Optional[datetime]
    ) -> str:
        count = len(supporting)
        date_str = cheque_date.strftime("%d %B %Y") if cheque_date else "the cheque date"
        return (
            f"{count} communication(s) preceding {date_str} indicate a "
            "pre-existing, legally enforceable debt. The cheque appears to have "
            "been issued for the discharge of that debt, satisfying the central "
            "requirement of Section 138 NI Act. The complaint has a strong "
            "evidentiary foundation."
        )
