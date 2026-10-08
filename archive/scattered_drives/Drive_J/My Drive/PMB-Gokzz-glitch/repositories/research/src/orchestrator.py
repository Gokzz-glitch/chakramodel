"""
Orchestrator
============
Coordinates the ingestion pipeline, Agent A (Classifier), and Agent B
(Chronologist) to produce a unified :class:`AnalysisResult`.

Usage
-----
::

    from src import Orchestrator

    orchestrator = Orchestrator()
    result = orchestrator.analyse(
        whatsapp_files=["exports/chat.txt"],
        email_files=["emails/thread.eml"],
        pdf_files=["ledgers/invoice_register.pdf"],
        cheque_date=datetime(2024, 3, 14),
    )

    print(result.cheque_context.value)
    print(result.summary)

    import json
    print(json.dumps(result.to_dict(), indent=2))
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from src.agents.classifier_agent import ClassifierAgent
from src.agents.chronologist_agent import ChronologistAgent
from src.ingestion.email_parser import EmailParser
from src.ingestion.pdf_parser import PDFParser
from src.ingestion.whatsapp_parser import WhatsAppParser
from src.models.communication import AnalysisResult, Communication

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    High-level coordinator for the Temporal NLP Debt Verification pipeline.

    Parameters
    ----------
    classifier :
        An instance of :class:`ClassifierAgent`.  A default instance is
        created if not supplied.
    chronologist :
        An instance of :class:`ChronologistAgent`.  A default instance is
        created if not supplied.
    min_classifier_confidence :
        Forwarded to :class:`ChronologistAgent` when creating a default
        instance.  Ignored if *chronologist* is explicitly provided.
    """

    def __init__(
        self,
        classifier: Optional[ClassifierAgent] = None,
        chronologist: Optional[ChronologistAgent] = None,
        min_classifier_confidence: float = 0.60,
    ) -> None:
        self.classifier = classifier or ClassifierAgent()
        self.chronologist = chronologist or ChronologistAgent(
            min_confidence=min_classifier_confidence
        )
        self._whatsapp_parser = WhatsAppParser()
        self._email_parser = EmailParser()
        self._pdf_parser = PDFParser()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def analyse(
        self,
        whatsapp_files: Optional[List[str]] = None,
        email_files: Optional[List[str]] = None,
        pdf_files: Optional[List[str]] = None,
        raw_communications: Optional[List[Communication]] = None,
        cheque_date: Optional[datetime] = None,
    ) -> AnalysisResult:
        """
        Run the full analysis pipeline.

        Parameters
        ----------
        whatsapp_files :
            Paths to WhatsApp chat export ``.txt`` files.
        email_files :
            Paths to ``.eml`` / mbox files.
        pdf_files :
            Paths to PDF ledger / invoice files.
        raw_communications :
            Pre-parsed :class:`Communication` objects (e.g., for testing).
            These are merged with any file-sourced communications.
        cheque_date :
            The date written on the cheque under scrutiny.

        Returns
        -------
        AnalysisResult
            Contains the legal conclusion, ordered timeline, and a human-
            readable summary.
        """
        all_comms: List[Communication] = list(raw_communications or [])

        # ---- Ingest files ----
        for path in (whatsapp_files or []):
            try:
                comms = self._whatsapp_parser.parse_file(path)
                logger.info("WhatsApp: parsed %d messages from %s", len(comms), path)
                all_comms.extend(comms)
            except Exception as exc:
                logger.warning("Failed to parse WhatsApp file %s: %s", path, exc)

        for path in (email_files or []):
            try:
                comms = self._email_parser.parse_file(path)
                logger.info("Email: parsed %d messages from %s", len(comms), path)
                all_comms.extend(comms)
            except Exception as exc:
                logger.warning("Failed to parse email file %s: %s", path, exc)

        for path in (pdf_files or []):
            try:
                comms = self._pdf_parser.parse_file(path)
                logger.info("PDF: parsed %d pages from %s", len(comms), path)
                all_comms.extend(comms)
            except Exception as exc:
                logger.warning("Failed to parse PDF file %s: %s", path, exc)

        # ---- Classify ----
        classified = self.classifier.classify_all(all_comms)
        logger.info("Classified %d communications total", len(classified))

        # ---- Build timeline & conclude ----
        result = self.chronologist.build_timeline(classified, cheque_date=cheque_date)
        logger.info("Analysis complete: %s", result.cheque_context.value)

        return result

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def analyse_text(
        self,
        whatsapp_text: Optional[str] = None,
        email_text: Optional[str] = None,
        cheque_date: Optional[datetime] = None,
    ) -> AnalysisResult:
        """
        Convenience method: accepts raw strings instead of file paths.

        Useful for quick programmatic analysis without creating temporary
        files on disk.
        """
        all_comms: List[Communication] = []

        if whatsapp_text:
            all_comms.extend(self._whatsapp_parser.parse_text(whatsapp_text))

        if email_text:
            all_comms.extend(self._email_parser.parse_text(email_text))

        classified = self.classifier.classify_all(all_comms)
        return self.chronologist.build_timeline(classified, cheque_date=cheque_date)

    def report(self, result: AnalysisResult, indent: int = 2) -> str:
        """Return a JSON string representation of *result*."""
        return json.dumps(result.to_dict(), indent=indent, ensure_ascii=False)
