"""
================================================================================
  CHAKRA MODEL PRO — INSPECTOR AUDIT SCRIPT
================================================================================
Inspector checks every nook & corner of chakra_combined.pdf against:
  1. literature_review.py  (source code)
  2. Opus.pdf              (425-page image PDF)
  3. mid.pdf               (45-page image PDF)

Verifies:
  A. Page count integrity
  B. Section structure & order
  C. Code content fidelity (line-by-line comparison)
  D. Image pixel-level integrity (hash comparison per page)
  E. File size & metadata
  F. Cover page data accuracy (TOC numbers, stats)
  G. Section divider presence
================================================================================
"""

import pymupdf
import hashlib
import os
import re
import sys
import datetime

# ── Source files ──────────────────────────────────────────────────────────────
SRC_PY    = r"J:\My Drive\downloads\literature_review.py"
SRC_PDF1  = r"J:\My Drive\downloads\Opus.pdf"
SRC_PDF2  = r"J:\My Drive\downloads\mid.pdf"
OUT_PDF   = r"M:\chakramodelpro\chakra_combined.pdf"
REPORT    = r"M:\chakramodelpro\inspection_report.md"

# ── Expected structure (from merger script) ────────────────────────────────────
# Page 1         : Cover page
# Pages 2 – 8   : Code pages (7 pages for 338 lines @ 55/page)
# Page 9         : Section divider §3 (Opus)
# Pages 10 – 434: Opus.pdf (425 pages)
# Page 435       : Section divider §4 (mid)
# Pages 436 – 480: mid.pdf (45 pages)
EXPECTED_COVER_PAGE      = 0       # index
EXPECTED_CODE_START      = 1       # index
EXPECTED_CODE_PAGES      = 7
EXPECTED_OPUS_DIVIDER    = 1 + 7   # index 8
EXPECTED_OPUS_START      = 1 + 7 + 1  # index 9
EXPECTED_OPUS_PAGES      = 425
EXPECTED_MID_DIVIDER     = 1 + 7 + 1 + 425  # index 434
EXPECTED_MID_START       = 1 + 7 + 1 + 425 + 1  # index 435
EXPECTED_MID_PAGES       = 45
EXPECTED_TOTAL           = 1 + 7 + 1 + 425 + 1 + 45  # 480

LINES_PER_CODE_PAGE = 55

PASS  = "[PASS]"
FAIL  = "[FAIL]"
WARN  = "[WARN]"
INFO  = "[INFO]"

findings   = []
errors     = []
warnings   = []
all_checks = []

def log(status, check_name, detail=""):
    tag = f"{status} {check_name}"
    if detail:
        tag += f"\n        -> {detail}"
    all_checks.append((status, check_name, detail))
    if status == FAIL:
        errors.append(check_name + (" | " + detail if detail else ""))
    elif status == WARN:
        warnings.append(check_name + (" | " + detail if detail else ""))
    print(tag)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

# ==============================================================================
# SECTION A: File existence & size checks
# ==============================================================================
print("\n" + "=" * 70)
print("  SECTION A: File Existence & Size")
print("=" * 70)

for label, path in [("literature_review.py", SRC_PY),
                     ("Opus.pdf",             SRC_PDF1),
                     ("mid.pdf",              SRC_PDF2),
                     ("chakra_combined.pdf",  OUT_PDF)]:
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / 1024 / 1024
        log(PASS, f"File exists: {label}", f"{size_mb:.2f} MB at {path}")
    else:
        log(FAIL, f"File MISSING: {label}", path)
        sys.exit("Cannot continue — output file missing.")

# Verify combined >= opus + mid (it should be, roughly)
sz_opus    = os.path.getsize(SRC_PDF1)
sz_mid     = os.path.getsize(SRC_PDF2)
sz_combined = os.path.getsize(OUT_PDF)
sz_py      = os.path.getsize(SRC_PY)

if sz_combined >= (sz_opus + sz_mid) * 0.85:
    log(PASS, "Combined PDF size plausible",
        f"combined={sz_combined/1e6:.1f}MB, opus={sz_opus/1e6:.1f}MB, mid={sz_mid/1e6:.1f}MB")
else:
    log(FAIL, "Combined PDF suspiciously small",
        f"combined={sz_combined/1e6:.1f}MB < 85% of (opus+mid)={((sz_opus+sz_mid)*0.85)/1e6:.1f}MB")

# ==============================================================================
# SECTION B: Page Count Integrity
# ==============================================================================
print("\n" + "=" * 70)
print("  SECTION B: Page Count Integrity")
print("=" * 70)

combined = pymupdf.open(OUT_PDF)
opus_src = pymupdf.open(SRC_PDF1)
mid_src  = pymupdf.open(SRC_PDF2)

actual_opus_pages = opus_src.page_count
actual_mid_pages  = mid_src.page_count
actual_total      = combined.page_count

with open(SRC_PY, "r", encoding="utf-8") as f:
    py_lines = f.readlines()
expected_code_pages = (len(py_lines) + LINES_PER_CODE_PAGE - 1) // LINES_PER_CODE_PAGE
expected_total = 1 + expected_code_pages + 1 + actual_opus_pages + 1 + actual_mid_pages

log(INFO, f"Opus.pdf source pages: {actual_opus_pages}")
log(INFO, f"mid.pdf source pages:  {actual_mid_pages}")
log(INFO, f"literature_review.py lines: {len(py_lines)} -> {expected_code_pages} code pages")
log(INFO, f"Expected total: {expected_total}, Actual total: {actual_total}")

if actual_total == expected_total:
    log(PASS, "Total page count matches", f"{actual_total} pages")
else:
    log(FAIL, "Total page count MISMATCH",
        f"expected={expected_total}, actual={actual_total}, diff={actual_total - expected_total}")

# ==============================================================================
# SECTION C: Structure & Section Order
# ==============================================================================
print("\n" + "=" * 70)
print("  SECTION C: Structure & Section Order")
print("=" * 70)

def get_page_dominant_color(page):
    """Sample top-left 100x50 area to detect dark header band."""
    mat = pymupdf.Matrix(0.1, 0.1)  # tiny render for speed
    pix = page.get_pixmap(matrix=mat)
    # First pixel color
    r = pix.samples[0]
    g = pix.samples[1]
    b = pix.samples[2]
    return (r, g, b)

def page_has_image(page):
    return len(page.get_images(full=True)) > 0

def page_has_text_containing(page, keyword):
    txt = page.get_text()
    return keyword.lower() in txt.lower()

# Check cover page (page index 0)
cover = combined[0]
if page_has_text_containing(cover, "CHAKRA MODEL PRO"):
    log(PASS, "Cover page present", "Contains 'CHAKRA MODEL PRO'")
else:
    log(FAIL, "Cover page missing or corrupt", "Text 'CHAKRA MODEL PRO' not found on page 1")

if page_has_text_containing(cover, "TABLE OF CONTENTS"):
    log(PASS, "Table of Contents present on cover")
else:
    log(WARN, "Table of Contents not detected on cover page")

if page_has_text_containing(cover, "Opus.pdf"):
    log(PASS, "Cover mentions Opus.pdf")
else:
    log(FAIL, "Cover missing Opus.pdf reference")

if page_has_text_containing(cover, "mid.pdf"):
    log(PASS, "Cover mentions mid.pdf")
else:
    log(FAIL, "Cover missing mid.pdf reference")

# Check code pages (pages 1 to expected_code_pages)
code_ok = 0
for ci in range(expected_code_pages):
    pg = combined[1 + ci]
    if page_has_text_containing(pg, "literature_review.py"):
        code_ok += 1
if code_ok == expected_code_pages:
    log(PASS, f"All {expected_code_pages} code pages have 'literature_review.py' header")
else:
    log(FAIL, f"Only {code_ok}/{expected_code_pages} code pages have correct header")

# Check Opus divider (page index = 1 + code_pages)
opus_div_idx = 1 + expected_code_pages
opus_div_page = combined[opus_div_idx]
if page_has_text_containing(opus_div_page, "Opus.pdf"):
    log(PASS, f"Opus.pdf section divider found at page {opus_div_idx + 1}")
else:
    log(FAIL, f"Opus.pdf divider MISSING at page {opus_div_idx + 1}")

# Check mid divider (page index = 1 + code_pages + 1 + opus_pages)
mid_div_idx = 1 + expected_code_pages + 1 + actual_opus_pages
mid_div_page = combined[mid_div_idx]
if page_has_text_containing(mid_div_page, "mid.pdf"):
    log(PASS, f"mid.pdf section divider found at page {mid_div_idx + 1}")
else:
    log(FAIL, f"mid.pdf divider MISSING at page {mid_div_idx + 1}")

# ==============================================================================
# SECTION D: Code Content Fidelity (Line-by-Line)
# ==============================================================================
print("\n" + "=" * 70)
print("  SECTION D: Code Content Fidelity (Line-by-Line)")
print("=" * 70)

with open(SRC_PY, "r", encoding="utf-8") as f:
    original_lines = [l.rstrip("\n") for l in f.readlines()]

# Extract all text from code pages in combined PDF
extracted_code_text = []
for ci in range(expected_code_pages):
    pg = combined[1 + ci]
    txt = pg.get_text("text")
    extracted_code_text.append(txt)

full_extracted = "\n".join(extracted_code_text)

# Count how many original lines appear verbatim (first 60 chars, stripped)
match_count   = 0
mismatch_lines = []
for i, orig_line in enumerate(original_lines):
    check = orig_line.strip()[:60]
    if len(check) >= 5 and check in full_extracted:
        match_count += 1
    elif len(check) >= 5:
        mismatch_lines.append((i + 1, orig_line[:80]))

total_checkable = sum(1 for l in original_lines if len(l.strip()) >= 5)
match_pct = (match_count / total_checkable * 100) if total_checkable else 0

log(INFO, f"Code lines checked: {total_checkable} non-trivial lines")
log(INFO, f"Lines found in combined PDF: {match_count} ({match_pct:.1f}%)")

if match_pct >= 95.0:
    log(PASS, f"Code fidelity EXCELLENT: {match_pct:.1f}% of lines verified")
elif match_pct >= 85.0:
    log(WARN, f"Code fidelity ACCEPTABLE: {match_pct:.1f}% of lines verified")
else:
    log(FAIL, f"Code fidelity LOW: only {match_pct:.1f}% of lines found in PDF")

if mismatch_lines:
    print(f"  {WARN} First 10 unverified lines:")
    for lineno, content in mismatch_lines[:10]:
        print(f"        Line {lineno}: {repr(content)}")

# ==============================================================================
# SECTION E: Image Pixel Integrity (Opus.pdf pages)
# ==============================================================================
print("\n" + "=" * 70)
print("  SECTION E: Image Integrity — Opus.pdf (sampling 10 pages)")
print("=" * 70)

opus_start_in_combined = 1 + expected_code_pages + 1  # skip cover+code+divider

# Sample 10 pages spread across Opus.pdf
sample_indices = list(range(0, actual_opus_pages, max(1, actual_opus_pages // 10)))[:10]
opus_mismatches = []

for src_idx in sample_indices:
    # Extract image hash from source
    src_page = opus_src[src_idx]
    src_imgs = src_page.get_images(full=True)
    if not src_imgs:
        continue
    src_xref = src_imgs[0][0]
    src_img_data = opus_src.extract_image(src_xref)["image"]
    src_hash = sha256_bytes(src_img_data)

    # Extract same position in combined
    comb_page = combined[opus_start_in_combined + src_idx]
    comb_imgs = comb_page.get_images(full=True)
    if not comb_imgs:
        log(FAIL, f"Opus page {src_idx+1}: NO IMAGE in combined PDF")
        opus_mismatches.append(src_idx)
        continue
    comb_xref = comb_imgs[0][0]
    comb_img_data = combined.extract_image(comb_xref)["image"]
    comb_hash = sha256_bytes(comb_img_data)

    if src_hash == comb_hash:
        log(PASS, f"Opus page {src_idx+1}: image hash MATCHES")
    else:
        log(FAIL, f"Opus page {src_idx+1}: image hash MISMATCH",
            f"src={src_hash[:16]}... comb={comb_hash[:16]}...")
        opus_mismatches.append(src_idx)

if not opus_mismatches:
    log(PASS, "All sampled Opus.pdf pages: images identical to source")
else:
    log(FAIL, f"{len(opus_mismatches)} Opus.pdf pages have image mismatches", str(opus_mismatches))

# ==============================================================================
# SECTION F: Image Pixel Integrity (mid.pdf pages)
# ==============================================================================
print("\n" + "=" * 70)
print("  SECTION F: Image Integrity — mid.pdf (all 45 pages)")
print("=" * 70)

mid_start_in_combined = 1 + expected_code_pages + 1 + actual_opus_pages + 1

mid_mismatches = []
for src_idx in range(actual_mid_pages):
    src_page = mid_src[src_idx]
    src_imgs = src_page.get_images(full=True)
    if not src_imgs:
        continue
    src_xref = src_imgs[0][0]
    src_img_data = mid_src.extract_image(src_xref)["image"]
    src_hash = sha256_bytes(src_img_data)

    comb_page = combined[mid_start_in_combined + src_idx]
    comb_imgs = comb_page.get_images(full=True)
    if not comb_imgs:
        log(FAIL, f"mid.pdf page {src_idx+1}: NO IMAGE in combined PDF")
        mid_mismatches.append(src_idx)
        continue
    comb_xref = comb_imgs[0][0]
    comb_img_data = combined.extract_image(comb_xref)["image"]
    comb_hash = sha256_bytes(comb_img_data)

    status = PASS if src_hash == comb_hash else FAIL
    if status == FAIL:
        mid_mismatches.append(src_idx)
        log(FAIL, f"mid.pdf page {src_idx+1}: image hash MISMATCH")
    else:
        log(PASS, f"mid.pdf page {src_idx+1}: image hash MATCHES")

if not mid_mismatches:
    log(PASS, "All 45 mid.pdf pages: images identical to source")
else:
    log(FAIL, f"{len(mid_mismatches)} mid.pdf pages have image mismatches", str(mid_mismatches))

# ==============================================================================
# SECTION G: Page Dimension Consistency
# ==============================================================================
print("\n" + "=" * 70)
print("  SECTION G: Page Dimension Consistency")
print("=" * 70)

dim_errors = []
# Opus pages in combined should match opus source
for src_idx in range(0, actual_opus_pages, max(1, actual_opus_pages // 20)):
    src_rect  = opus_src[src_idx].rect
    comb_rect = combined[opus_start_in_combined + src_idx].rect
    if abs(src_rect.width - comb_rect.width) > 1 or abs(src_rect.height - comb_rect.height) > 1:
        dim_errors.append(f"Opus p{src_idx+1}: src={src_rect.width:.0f}x{src_rect.height:.0f} "
                          f"vs comb={comb_rect.width:.0f}x{comb_rect.height:.0f}")

for src_idx in range(actual_mid_pages):
    src_rect  = mid_src[src_idx].rect
    comb_rect = combined[mid_start_in_combined + src_idx].rect
    if abs(src_rect.width - comb_rect.width) > 1 or abs(src_rect.height - comb_rect.height) > 1:
        dim_errors.append(f"mid p{src_idx+1}: src={src_rect.width:.0f}x{src_rect.height:.0f} "
                          f"vs comb={comb_rect.width:.0f}x{comb_rect.height:.0f}")

if not dim_errors:
    log(PASS, "All sampled page dimensions match between source and combined")
else:
    for e in dim_errors:
        log(FAIL, "Page dimension MISMATCH", e)

# ==============================================================================
# SECTION H: Cover Page TOC Number Accuracy (PRECISE)
# ==============================================================================
print("\n" + "=" * 70)
print("  SECTION H: Cover Page TOC Number Accuracy (Precise)")
print("=" * 70)

cover_text = combined[0].get_text()

# Calculate exact expected page numbers (human 1-indexed)
# Layout: [1 cover][code_pages...][1 divider][opus_pages...][1 divider][mid_pages...]
code_end_pg   = 1 + expected_code_pages              # last code page
opus_start_pg = code_end_pg + 2                      # after divider
opus_end_pg   = opus_start_pg + actual_opus_pages - 1
mid_start_pg  = opus_end_pg + 2                      # after divider
mid_end_pg    = mid_start_pg + actual_mid_pages - 1
correct_total = 1 + expected_code_pages + 1 + actual_opus_pages + 1 + actual_mid_pages

log(INFO, f"Correct total pages: {correct_total}")
log(INFO, f"Correct TOC: Code=2-{code_end_pg}, Opus={opus_start_pg}-{opus_end_pg}, mid={mid_start_pg}-{mid_end_pg}")

# Check each expected number appears in cover text
precise_checks = [
    (str(expected_code_pages),    f"Code page count ({expected_code_pages})"),
    (str(code_end_pg),            f"Code section end pg ({code_end_pg})"),
    (str(actual_opus_pages),      f"Opus page count ({actual_opus_pages})"),
    (str(opus_start_pg),          f"Opus section start pg ({opus_start_pg})"),
    (str(opus_end_pg),            f"Opus section end pg ({opus_end_pg})"),
    (str(actual_mid_pages),       f"mid page count ({actual_mid_pages})"),
    (str(mid_start_pg),           f"mid section start pg ({mid_start_pg})"),
    (str(mid_end_pg),             f"mid section end pg ({mid_end_pg})"),
    (str(correct_total),          f"Total pages ({correct_total})"),
]
toc_fails = 0
for needle, desc in precise_checks:
    if needle in cover_text:
        log(PASS, f"Cover TOC: {desc} found correctly")
    else:
        log(FAIL, f"Cover TOC WRONG/MISSING: {desc}",
            f"Expected '{needle}' in cover text but not found")
        toc_fails += 1

if toc_fails == 0:
    log(PASS, "All TOC page numbers are precise and correct")
else:
    log(FAIL, f"{toc_fails} TOC number(s) incorrect on cover page")


# ==============================================================================
# SECTION I: Metadata & Creator Info
# ==============================================================================
print("\n" + "=" * 70)
print("  SECTION I: Metadata")
print("=" * 70)

meta = combined.metadata
log(INFO, f"Combined PDF producer: {meta.get('producer', 'N/A')}")
log(INFO, f"Combined PDF creator:  {meta.get('creator', 'N/A')}")
log(INFO, f"Combined PDF format:   {meta.get('format', 'N/A')}")
log(INFO, f"Encryption:            {meta.get('encryption', 'None')}")

if meta.get("encryption") is None:
    log(PASS, "No encryption on combined PDF (accessible)")
else:
    log(WARN, "Combined PDF is encrypted", str(meta.get("encryption")))

# ==============================================================================
# CLOSE DOCS
# ==============================================================================
combined.close()
opus_src.close()
mid_src.close()

# ==============================================================================
# FINAL REPORT
# ==============================================================================
print("\n" + "=" * 70)
print("  INSPECTOR FINAL VERDICT")
print("=" * 70)

total_checks = len(all_checks)
pass_count   = sum(1 for s, _, _ in all_checks if s == PASS)
fail_count   = len(errors)
warn_count   = len(warnings)
info_count   = sum(1 for s, _, _ in all_checks if s == INFO)

print(f"  Total checks run : {total_checks}")
print(f"  PASS             : {pass_count}")
print(f"  FAIL             : {fail_count}")
print(f"  WARN             : {warn_count}")
print(f"  INFO             : {info_count}")
print()

if fail_count == 0 and warn_count == 0:
    verdict = "PERFECT - No issues found."
elif fail_count == 0:
    verdict = f"PASS WITH WARNINGS - {warn_count} warning(s), 0 failures."
else:
    verdict = f"FAILED - {fail_count} CRITICAL issue(s) found."

print(f"  VERDICT: {verdict}")

if errors:
    print("\n  CRITICAL FAILURES:")
    for e in errors:
        print(f"    {FAIL} {e}")
if warnings:
    print("\n  WARNINGS:")
    for w in warnings:
        print(f"    {WARN} {w}")

# ── Write Markdown Report ─────────────────────────────────────────────────────
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
with open(REPORT, "w", encoding="utf-8") as rpt:
    rpt.write(f"# Chakra Model Pro - Inspection Report\n")
    rpt.write(f"> **Inspector Run:** {now}  \n")
    rpt.write(f"> **Verdict:** {verdict}\n\n")
    rpt.write(f"## Summary\n\n")
    rpt.write(f"| Metric | Count |\n|---|---|\n")
    rpt.write(f"| Total Checks | {total_checks} |\n")
    rpt.write(f"| PASS | {pass_count} |\n")
    rpt.write(f"| FAIL | {fail_count} |\n")
    rpt.write(f"| WARN | {warn_count} |\n")
    rpt.write(f"| INFO | {info_count} |\n\n")

    if errors:
        rpt.write(f"## Critical Failures\n\n")
        for e in errors:
            rpt.write(f"- {FAIL} {e}\n")
        rpt.write("\n")

    if warnings:
        rpt.write(f"## Warnings\n\n")
        for w in warnings:
            rpt.write(f"- {WARN} {w}\n")
        rpt.write("\n")

    rpt.write(f"## Full Check Log\n\n")
    for status, name, detail in all_checks:
        rpt.write(f"- `{status}` **{name}**")
        if detail:
            rpt.write(f"  \n  _{detail}_")
        rpt.write("\n")

print(f"\n  Report saved: {REPORT}")
print("=" * 70)
