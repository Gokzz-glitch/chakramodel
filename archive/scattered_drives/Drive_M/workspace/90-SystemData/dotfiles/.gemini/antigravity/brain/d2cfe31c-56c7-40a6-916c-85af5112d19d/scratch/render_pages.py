"""
Render sample pages from Opus.pdf and mid.pdf as PNG images for visual inspection.
"""
import pymupdf
import os

OUT_DIR = r"C:\Users\imgk3\.gemini\antigravity\brain\d2cfe31c-56c7-40a6-916c-85af5112d19d\scratch\page_samples"
os.makedirs(OUT_DIR, exist_ok=True)

# ── Opus.pdf: render pages 1,2,3, 50, 100, 150, 200, 250, 300, 350, 400, 424 ──
print("Rendering Opus.pdf samples...")
doc = pymupdf.open(r"J:\My Drive\downloads\Opus.pdf")
opus_samples = [0, 1, 2, 49, 99, 149, 199, 249, 299, 349, 399, 423]
for i in opus_samples:
    page = doc[i]
    mat = pymupdf.Matrix(0.5, 0.5)   # 50% scale for speed
    pix = page.get_pixmap(matrix=mat)
    out = os.path.join(OUT_DIR, f"opus_page_{i+1:04d}.png")
    pix.save(out)
    print(f"  Saved: {out}")
doc.close()

# ── mid.pdf: render all 45 pages ──────────────────────────────────────────────
print("Rendering mid.pdf samples...")
doc = pymupdf.open(r"J:\My Drive\downloads\mid.pdf")
for i in range(doc.page_count):
    page = doc[i]
    mat = pymupdf.Matrix(0.6, 0.6)
    pix = page.get_pixmap(matrix=mat)
    out = os.path.join(OUT_DIR, f"mid_page_{i+1:04d}.png")
    pix.save(out)
    print(f"  Saved: {out}")
doc.close()

print("Done.")
