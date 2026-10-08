"""
Temporal NLP for Legally Enforceable Debt Verification
=======================================================
A multi-agent NLP system that analyses unstructured business communications
(WhatsApp exports, email threads, ledger PDFs) to determine whether a cheque
was issued for a pre-existing, legally enforceable debt under Section 138 of
the Negotiable Instruments Act, 1881.
"""

from .orchestrator import Orchestrator

__all__ = ["Orchestrator"]
