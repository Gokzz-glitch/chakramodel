"""
etl/pdf_extractor.py
SmartSalai Edge-Sentinel — Persona 6: ETL Data Scavenger
Stage 1 of 4: PDF → Raw Text

FUNCTION:
  Extracts text from government legal PDFs (MoRTH Gazette, TN State GOs).
  Two-pass strategy:
    Pass 1 (DIGITAL): pdfplumber — fast, lossless for text-layer PDFs.
    Pass 2 (OCR):     pdf2image → pytesseract (Tesseract 5.x, `ind` + `eng`
                      tessdata) — for fully scanned/image-based gazette pages.

SCANNED GAZETTE CHARACTERISTICS:
  - Indian gazette PDFs are frequently 150–300 DPI scans.
  - Multi-column layout (2-column standard for Gazette Extraordinary).
  - Mixed Devanagari/Tamil + Roman script (bilingual gazette headers).
  - Low-contrast watermarks and government seals — pre-processing required.

INPUT  : Path to a single PDF file.
OUTPUT : ExtractionResult dataclass — per-page raw text + metadata.

HUMAN OPERATOR NOTE:
  Drop raw PDF files into the `/raw_data/` directory.
  DO NOT place password-protected or DRM-encrypted PDFs — they will be
  quarantined with a QUARANTINE_ENCRYPTED log entry.
  Authenticated portal downloads (e.g., IDD, MoRTH VAHAN) MUST be done
  manually and dropped into `/raw_data/` — no scraper will be written.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict

import pdfplumber

logger = logging.getLogger("edge_sentinel.etl.pdf_extractor")
logger.setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum character yield from pdfplumber before falling back to OCR.
# Indian gazette text pages have ~800–2000 chars; below this = likely scanned.
MIN_DIGITAL_CHARS_PER_PAGE: int = 80

# Tesseract language pack: "hin+tam+eng" for Hindi + Tamil + English.
# Requires tessdata for both scripts: `apt install tesseract-ocr-hin tesseract-ocr-tam`
TESSERACT_LANG: str = "hin+tam+eng"

# DPI for pdf2image rasterization. 300 DPI = acceptable OCR accuracy for
# 8pt gazette font. Higher DPI → better accuracy, much higher RAM.
OCR_RASTER_DPI: int = 300

# Tesseract --psm values:
#   3 = Fully automatic page segmentation (default)
#   4 = Assume a single column of text of variable sizes
#   6 = Assume a single uniform block of text
# Indian gazette: 2-column, so we use psm=3 and rely on Tesseract's layout analysis.
TESSERACT_PSM: int = 3

# Regex patterns for Indian legal section headers — used for metadata tagging
INDIAN_SECTION_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:Section|Sec\.?|SECTION|धारा|பிரிவு)\s+(\d+[A-Z]?(?:\([a-z0-9]+\))*)",
    re.MULTILINE,
)
GO_NOTIFICATION_PATTERN = re.compile(
    r"G\.O\.\s*\(Ms\)[\.\s]*No[\.\s]*(\d+)",
    re.IGNORECASE,
)
GAZETTE_REF_PATTERN = re.compile(
    r"S\.O\.[\s]*(\d+)\s*\(E\)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class ExtractionMethod(Enum):
    DIGITAL_PDFPLUMBER = "DIGITAL_PDFPLUMBER"
    OCR_TESSERACT      = "OCR_TESSERACT"
    HYBRID             = "HYBRID"          # Some pages digital, some OCR


class ExtractionStatus(Enum):
    SUCCESS     = "SUCCESS"
    PARTIAL     = "PARTIAL"     # Some pages failed — extraction continued
    QUARANTINED = "QUARANTINED" # Encrypted / DRM / corrupt — skipped entirely
    FAILED      = "FAILED"      # Unrecoverable error


@dataclass
class PageText:
    """
    Text content of a single PDF page with extraction provenance.
    """
    page_number: int          # 1-indexed
    raw_text: str             # Raw extracted text (no cleaning yet — Stage 2 owns that)
    method: ExtractionMethod
    char_count: int
    ocr_confidence: Optional[float] = None  # Mean Tesseract confidence [0–100], None if digital
    extraction_time_ms: float = 0.0


@dataclass
class ExtractionResult:
    """
    Full extraction result for one PDF file.
    Passed downstream to text_chunker.py (Stage 2).
    """
    source_path: str
    file_sha256: str             # SHA-256 of raw PDF bytes — deduplication key
    total_pages: int
    extracted_pages: List[PageText] = field(default_factory=list)
    status: ExtractionStatus = ExtractionStatus.SUCCESS
    method: ExtractionMethod = ExtractionMethod.DIGITAL_PDFPLUMBER
    doc_type: Optional[str] = None   # e.g. "GAZETTE_CENTRAL", "TN_STATE_GO", "MVA_ACT"
    gazette_ref: Optional[str] = None
    go_ref: Optional[str] = None
    sections_detected: List[str] = field(default_factory=list)
    extraction_timestamp_epoch_ms: int = 0
    error_log: List[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        """Returns concatenated text of all successfully extracted pages."""
        return "\n\n".join(p.raw_text for p in self.extracted_pages if p.raw_text.strip())

    @property
    def pages_failed(self) -> int:
        return self.total_pages - len(self.extracted_pages)


# ---------------------------------------------------------------------------
# Image Pre-Processing (for scanned gazette pages)
# ---------------------------------------------------------------------------

def _preprocess_page_image(pil_image: object) -> object:
    """
    Pre-process a PIL Image for improved OCR accuracy on Indian gazette scans.
    Operations:
      1. Convert to greyscale
      2. Adaptive thresholding (binarization) via Pillow/ImageFilter
      3. Mild sharpening

    This replaces impractical OpenCV dependency with Pillow-only operations
    for maximum portability on constrained Android-host build environments.
    """
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps

    img = pil_image.convert("L")          # Greyscale
    img = ImageOps.autocontrast(img, cutoff=2)  # Auto-contrast — removes watermarks
    img = img.filter(ImageFilter.SHARPEN)       # Edge sharpening for thin serif fonts
    # Binary threshold at 128 — improves OCR on low-contrast gazette prints
    img = img.point(lambda px: 255 if px > 128 else 0, "1")
    img = img.convert("RGB")  # Tesseract expects RGB
    return img


# ---------------------------------------------------------------------------
# PDF Extractor
# ---------------------------------------------------------------------------

class PDFExtractor:
    """
    Two-pass PDF text extractor for Indian government legal documents.

    Pass 1 (pdfplumber): Attempts digital text extraction.
    Pass 2 (Tesseract OCR): Activated per-page if digital yield < MIN_DIGITAL_CHARS_PER_PAGE.

    Dependency matrix:
      Always required : pdfplumber
      OCR fallback    : pdf2image, pytesseract, Pillow
                        System: Tesseract 5.x binary + tessdata (hin, tam, eng)

    Instantiation is cheap — no models loaded at __init__.
    """

    def __init__(
        self,
        ocr_fallback: bool = True,
        min_chars_threshold: int = MIN_DIGITAL_CHARS_PER_PAGE,
        tesseract_lang: str = TESSERACT_LANG,
        ocr_dpi: int = OCR_RASTER_DPI,
    ) -> None:
        self.ocr_fallback = ocr_fallback
        self.min_chars_threshold = min_chars_threshold
        self.tesseract_lang = tesseract_lang
        self.ocr_dpi = ocr_dpi
        self._ocr_available: Optional[bool] = None  # Lazy-checked on first OCR attempt

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, pdf_path: str | Path) -> ExtractionResult:
        """
        Main entry point. Extracts text from one PDF file.

        Returns ExtractionResult with status = QUARANTINED if the file is
        encrypted, FAILED if unreadable, PARTIAL if some pages failed,
        SUCCESS if all pages extracted.
        """
        pdf_path = Path(pdf_path)
        ts = int(time.time() * 1000)
        logger.info(f"[P6/Stage1] Extracting: {pdf_path.name}")

        if not pdf_path.exists():
            return self._make_failed(str(pdf_path), f"File not found: {pdf_path}", ts)

        try:
            file_sha256 = self._sha256(pdf_path)
        except OSError as exc:
            return self._make_failed(str(pdf_path), f"Cannot read file: {exc}", ts)

        # Attempt pdfplumber open — catches encrypted PDFs early
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                if getattr(pdf, "is_encrypted", False):
                    logger.warning(f"[P6/Stage1] QUARANTINE: {pdf_path.name} — encrypted")
                    return ExtractionResult(
                        source_path=str(pdf_path),
                        file_sha256=file_sha256,
                        total_pages=0,
                        status=ExtractionStatus.QUARANTINED,
                        extraction_timestamp_epoch_ms=ts,
                        error_log=["QUARANTINE_ENCRYPTED: PDF is password-protected."],
                    )
                total_pages = len(pdf.pages)
                doc_type = self._classify_doc_type(pdf_path.stem)
                result = ExtractionResult(
                    source_path=str(pdf_path),
                    file_sha256=file_sha256,
                    total_pages=total_pages,
                    doc_type=doc_type,
                    extraction_timestamp_epoch_ms=ts,
                )
                methods_used: set = set()

                for i, page in enumerate(pdf.pages, start=1):
                    page_result = self._extract_page(pdf_path, i, page)
                    if page_result is None:
                        result.error_log.append(f"Page {i}: extraction returned None — skipped.")
                        continue
                    result.extracted_pages.append(page_result)
                    methods_used.add(page_result.method)

        except pdfplumber.pdfminer.pdfparser.PDFSyntaxError as exc:
            return self._make_failed(str(pdf_path), f"PDF syntax error: {exc}", ts)
        except Exception as exc:
            return self._make_failed(str(pdf_path), f"Unexpected error: {exc}", ts)

        # Resolve overall status
        n_extracted = len(result.extracted_pages)
        if n_extracted == 0:
            result.status = ExtractionStatus.FAILED
        elif n_extracted < total_pages:
            result.status = ExtractionStatus.PARTIAL
        else:
            result.status = ExtractionStatus.SUCCESS

        # Determine overall method
        if len(methods_used) > 1:
            result.method = ExtractionMethod.HYBRID
        elif ExtractionMethod.OCR_TESSERACT in methods_used:
            result.method = ExtractionMethod.OCR_TESSERACT
        else:
            result.method = ExtractionMethod.DIGITAL_PDFPLUMBER

        # Post-extraction metadata detection on full concatenated text
        full_text = result.full_text
        result.sections_detected = INDIAN_SECTION_PATTERN.findall(full_text)
        gz = GAZETTE_REF_PATTERN.search(full_text)
        result.gazette_ref = gz.group(0) if gz else None
        go = GO_NOTIFICATION_PATTERN.search(full_text)
        result.go_ref = go.group(0) if go else None

        logger.info(
            f"[P6/Stage1] Done: {pdf_path.name} | pages={n_extracted}/{total_pages} "
            f"| method={result.method.value} | status={result.status.value} "
            f"| sections_detected={len(result.sections_detected)}"
        )
        return result

    # ------------------------------------------------------------------
    # Internal: Page-Level Extraction
    # ------------------------------------------------------------------

    def _extract_page(
        self,
        pdf_path: Path,
        page_num: int,
        plumber_page: object,
    ) -> Optional[PageText]:
        """
        Extracts a single page. Returns PageText or None on hard failure.
        """
        t0 = time.monotonic()

        # --- Pass 1: pdfplumber digital extraction ---
        try:
            digital_text: str = plumber_page.extract_text(
                x_tolerance=3,
                y_tolerance=3,
                layout=True,        # Preserves reading order for multi-column
                layout_width_chars=200,
            ) or ""
        except Exception as exc:
            logger.warning(f"[P6/Stage1] Page {page_num}: pdfplumber error — {exc}")
            digital_text = ""

        if len(digital_text.strip()) >= self.min_chars_threshold:
            return PageText(
                page_number=page_num,
                raw_text=digital_text,
                method=ExtractionMethod.DIGITAL_PDFPLUMBER,
                char_count=len(digital_text),
                extraction_time_ms=(time.monotonic() - t0) * 1000,
            )

        # --- Pass 2: OCR fallback ---
        if not self.ocr_fallback:
            logger.debug(f"[P6/Stage1] Page {page_num}: low digital yield ({len(digital_text.strip())} chars) — OCR disabled.")
            return PageText(
                page_number=page_num,
                raw_text=digital_text,
                method=ExtractionMethod.DIGITAL_PDFPLUMBER,
                char_count=len(digital_text),
                extraction_time_ms=(time.monotonic() - t0) * 1000,
            )

        if not self._check_ocr_available():
            logger.warning(
                f"[P6/Stage1] Page {page_num}: OCR libraries unavailable. "
                "Install: pdf2image pytesseract Pillow + Tesseract binary."
            )
            return PageText(
                page_number=page_num,
                raw_text=digital_text,
                method=ExtractionMethod.DIGITAL_PDFPLUMBER,
                char_count=len(digital_text),
                extraction_time_ms=(time.monotonic() - t0) * 1000,
            )

        logger.debug(
            f"[P6/Stage1] Page {page_num}: digital yield {len(digital_text.strip())} chars "
            f"< threshold {self.min_chars_threshold} — switching to OCR."
        )
        return self._ocr_page(pdf_path, page_num, t0)

    def _ocr_page(self, pdf_path: Path, page_num: int, t0: float) -> Optional[PageText]:
        """
        Rasterize the specific page and run Tesseract OCR on it.
        Only the target page is rasterized to preserve RAM.
        """
        try:
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(
                str(pdf_path),
                dpi=self.ocr_dpi,
                first_page=page_num,
                last_page=page_num,
                fmt="jpeg",
                jpegopt={"quality": 92, "progressive": True},
            )
            if not images:
                logger.error(f"[P6/Stage1] Page {page_num}: pdf2image returned no images.")
                return None

            img = _preprocess_page_image(images[0])

            # Tesseract config: --psm 3 (auto layout) + OSD disabled for speed
            custom_config = (
                f"--psm {TESSERACT_PSM} "
                "--oem 3 "                    # LSTM engine
                "-c preserve_interword_spaces=1"
            )
            ocr_data: dict = pytesseract.image_to_data(
                img,
                lang=self.tesseract_lang,
                config=custom_config,
                output_type=pytesseract.Output.DICT,
            )

            # Reconstruct text and compute mean confidence (filter conf=-1 = noise)
            words      = ocr_data["text"]
            confs      = [int(c) for c in ocr_data["conf"] if int(c) >= 0]
            mean_conf  = sum(confs) / len(confs) if confs else 0.0
            ocr_text   = " ".join(w for w in words if w.strip())

            return PageText(
                page_number=page_num,
                raw_text=ocr_text,
                method=ExtractionMethod.OCR_TESSERACT,
                char_count=len(ocr_text),
                ocr_confidence=mean_conf,
                extraction_time_ms=(time.monotonic() - t0) * 1000,
            )

        except Exception as exc:
            logger.error(f"[P6/Stage1] Page {page_num}: OCR failed — {exc}")
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_ocr_available(self) -> bool:
        if self._ocr_available is not None:
            return self._ocr_available
        try:
            import pdf2image    # noqa: F401
            import pytesseract  # noqa: F401
            import PIL          # noqa: F401
            self._ocr_available = True
        except ImportError:
            self._ocr_available = False
        return self._ocr_available

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _classify_doc_type(stem: str) -> str:
        """
        Heuristic document type classification from filename stem.
        Returns a string tag for downstream metadata.
        """
        stem_lower = stem.lower()
        if "gazette" in stem_lower or "s_o" in stem_lower or "so_" in stem_lower:
            return "GAZETTE_CENTRAL"
        if "g_o" in stem_lower or "go_" in stem_lower or "state" in stem_lower:
            return "TN_STATE_GO"
        if "mva" in stem_lower or "motor_vehicles" in stem_lower:
            return "MVA_ACT"
        if "irad" in stem_lower:
            return "IRAD_DATASET"
        return "UNKNOWN"

    @staticmethod
    def _make_failed(path: str, reason: str, ts: int) -> ExtractionResult:
        logger.error(f"[P6/Stage1] FAILED: {path} — {reason}")
        return ExtractionResult(
            source_path=path,
            file_sha256="",
            total_pages=0,
            status=ExtractionStatus.FAILED,
            extraction_timestamp_epoch_ms=ts,
            error_log=[reason],
        )
