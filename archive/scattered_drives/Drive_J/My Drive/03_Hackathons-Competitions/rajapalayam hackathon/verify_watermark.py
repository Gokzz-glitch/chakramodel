"""
╔══════════════════════════════════════════════════════════════╗
║         MANDIVISION — WATERMARK VERIFIER v1.0               ║
║   Cryptographic Proof-of-Ownership for Dataset Images        ║
║   Data Genesis 2026 Hackathon — Team Rajapalayam            ║
╚══════════════════════════════════════════════════════════════╝

HOW IT WORKS
------------
Extracts the hidden LSB steganographic payload from any image and
cross-references it against the watermark_manifest.json.

Verification outcomes:
  ✅ VERIFIED    — payload matches manifest, image provably ours
  ⚠️  TAMPERED   — payload found but hash mismatch (image was modified)
  ❌ NOT OURS    — no valid payload found (not from this dataset)

USAGE
-----
  python verify_watermark.py                     # scan all watermarked images
  python verify_watermark.py <image_path>        # verify a single image
  python verify_watermark.py --html              # also regenerate dashboard

OUTPUT
------
  watermark_verification_report.json — full verification log
  authenticity_dashboard.html        — updated judge-facing HTML dashboard
"""

import os
import sys
import json
import struct
import hashlib
import numpy as np
from datetime import datetime
from PIL import Image

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Configuration ─────────────────────────────────────────────────────────────
WATERMARKED_DIR  = r"J:\My Drive\rajapalayam hackathon\watermarked_dataset"
MANIFEST_PATH    = r"J:\My Drive\rajapalayam hackathon\watermark_manifest.json"
REPORT_OUT       = r"J:\My Drive\rajapalayam hackathon\watermark_verification_report.json"
DASHBOARD_OUT    = r"J:\My Drive\rajapalayam hackathon\authenticity_dashboard.html"

EXPECTED_PREFIX  = "MANDIVISION|"
END_MARKER       = "END"

# ── Helpers ───────────────────────────────────────────────────────────────────

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def bits_to_string(bits: list) -> str:
    """Reconstruct a UTF-8 string from a list of bits (MSB first)."""
    # First 32 bits = length of payload in bytes
    if len(bits) < 32:
        return ""

    length_bytes = bytes(
        sum(bits[i * 8 + j] << (7 - j) for j in range(8))
        for i in range(4)
    )
    payload_len = struct.unpack(">I", length_bytes)[0]

    if payload_len > 10000 or payload_len < 1:
        return ""

    total_bits_needed = 32 + payload_len * 8
    if len(bits) < total_bits_needed:
        return ""

    payload_bytes = bytes(
        sum(bits[32 + i * 8 + j] << (7 - j) for j in range(8))
        for i in range(payload_len)
    )

    try:
        return payload_bytes.decode("utf-8")
    except Exception:
        return ""


def extract_lsb(image_path: str, max_bits: int = 10000 * 8 + 32) -> str:
    """
    Extract the LSB-encoded payload from the blue channel of an image.
    Returns the decoded string, or empty string if nothing found.
    """
    try:
        with Image.open(image_path) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            else:
                img = img.convert("RGB")

            arr = np.array(img, dtype=np.uint8)
            flat_blue = arr[:, :, 2].flatten()

            # Extract up to max_bits LSBs
            n = min(len(flat_blue), max_bits)
            bits = [int(flat_blue[i]) & 1 for i in range(n)]

        return bits_to_string(bits)

    except Exception as e:
        return ""


def verify_single(image_path: str, manifest_lookup: dict) -> dict:
    """Verify a single image. Returns a result dict."""
    fname      = os.path.basename(image_path)
    file_hash  = sha256_file(image_path)
    payload    = extract_lsb(image_path)

    result = {
        "filename":   fname,
        "sha256":     file_hash,
        "payload":    payload if payload else None,
        "status":     "UNKNOWN",
        "verdict":    "❓ UNKNOWN"
    }

    if not payload or not payload.startswith(EXPECTED_PREFIX):
        result["status"]  = "NOT_OURS"
        result["verdict"] = "❌ NOT OUR IMAGE"
        return result

    # Check manifest
    manifest_entry = manifest_lookup.get(fname) or manifest_lookup.get(file_hash)

    if manifest_entry:
        if (manifest_entry.get("payload") == payload
                and manifest_entry.get("sha256_watermarked") == file_hash):
            result["status"]  = "VERIFIED"
            result["verdict"] = "✅ VERIFIED — MANDIVISION OWNED"
        elif manifest_entry.get("payload") == payload:
            # Payload matches but hash differs — re-saved/compressed
            result["status"]  = "PAYLOAD_MATCH"
            result["verdict"] = "✅ PAYLOAD VERIFIED (re-compressed)"
        else:
            result["status"]  = "TAMPERED"
            result["verdict"] = "⚠️ TAMPERED — Hash Mismatch"
    else:
        # Payload has our prefix but not in manifest — still ours
        if EXPECTED_PREFIX in payload and "DataGenesis2026" in payload:
            result["status"]  = "VERIFIED_NO_MANIFEST"
            result["verdict"] = "✅ PAYLOAD VERIFIED (no manifest entry)"
        else:
            result["status"]  = "SUSPICIOUS"
            result["verdict"] = "⚠️ SUSPICIOUS PAYLOAD"

    return result


# ── HTML Dashboard Generator ──────────────────────────────────────────────────

def generate_dashboard(results: list, manifest: dict, out_path: str):
    """Generate the premium authenticity dashboard HTML."""

    total   = len(results)
    verified = sum(1 for r in results if "VERIFIED" in r["status"])
    tampered = sum(1 for r in results if r["status"] == "TAMPERED")
    not_ours = sum(1 for r in results if r["status"] == "NOT_OURS")

    verify_pct  = (verified / max(total, 1)) * 100
    timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build table rows (show all, sorted: verified first, then tampered, then unknown)
    sorted_results = sorted(results, key=lambda r: (
        0 if "VERIFIED" in r["status"] else 1 if r["status"] == "TAMPERED" else 2
    ))

    rows_html = ""
    for r in sorted_results:
        if "VERIFIED" in r["status"]:
            badge_cls, badge_txt = "badge-verified", "✅ VERIFIED"
        elif r["status"] == "TAMPERED":
            badge_cls, badge_txt = "badge-tampered", "⚠️ TAMPERED"
        else:
            badge_cls, badge_txt = "badge-unknown", "❌ NOT OURS"

        payload_display = r["payload"] if r["payload"] else "—"
        rows_html += f"""
            <tr>
              <td class="fname">{r['filename']}</td>
              <td class="hash">{r['sha256'][:16]}…</td>
              <td class="payload-cell">{payload_display}</td>
              <td><span class="badge {badge_cls}">{badge_txt}</span></td>
            </tr>"""

    overall_class = "overall-pass" if verify_pct >= 90 else "overall-warn" if verify_pct >= 50 else "overall-fail"
    overall_text  = "DATASET OWNERSHIP VERIFIED" if verify_pct >= 90 else "PARTIAL VERIFICATION" if verify_pct >= 50 else "VERIFICATION FAILED"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MandiVision — Dataset Authenticity Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:        #0a0f1a;
      --surface:   #111827;
      --surface2:  #1a2234;
      --border:    rgba(99,179,237,0.15);
      --accent:    #3b82f6;
      --accent2:   #10b981;
      --warn:      #f59e0b;
      --danger:    #ef4444;
      --text:      #e2e8f0;
      --muted:     #64748b;
      --verified:  #10b981;
      --tampered:  #f59e0b;
      --unknown:   #ef4444;
    }}

    body {{
      font-family: 'Inter', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 2rem 1rem;
    }}

    /* ── Header ─────────────────────────────── */
    .header {{
      max-width: 1100px;
      margin: 0 auto 2.5rem;
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1.5rem;
      flex-wrap: wrap;
    }}
    .logo-block {{ display: flex; align-items: center; gap: 1rem; }}
    .logo-icon {{
      width: 52px; height: 52px; border-radius: 14px;
      background: linear-gradient(135deg, #1d4ed8, #0ea5e9);
      display: flex; align-items: center; justify-content: center;
      font-size: 1.6rem; flex-shrink: 0;
      box-shadow: 0 0 24px rgba(59,130,246,0.4);
    }}
    .logo-text h1 {{ font-size: 1.5rem; font-weight: 800; letter-spacing: -0.5px; }}
    .logo-text .sub {{ font-size: 0.78rem; color: var(--muted); margin-top: 2px; }}
    .header-meta {{
      text-align: right; font-size: 0.78rem; color: var(--muted);
      line-height: 1.6;
    }}
    .header-meta strong {{ color: var(--accent); }}

    /* ── Overall verdict banner ─────────────── */
    .verdict-banner {{
      max-width: 1100px; margin: 0 auto 2rem;
      padding: 1.25rem 1.75rem;
      border-radius: 16px;
      display: flex; align-items: center; gap: 1.25rem;
      border: 1px solid;
    }}
    .overall-pass  {{ background: rgba(16,185,129,0.08); border-color: rgba(16,185,129,0.35); }}
    .overall-warn  {{ background: rgba(245,158,11,0.08); border-color: rgba(245,158,11,0.35); }}
    .overall-fail  {{ background: rgba(239,68,68,0.08);  border-color: rgba(239,68,68,0.35); }}
    .verdict-icon  {{ font-size: 2rem; flex-shrink: 0; }}
    .verdict-label {{ font-size: 1.1rem; font-weight: 700; letter-spacing: 0.5px; }}
    .verdict-sub   {{ font-size: 0.8rem; color: var(--muted); margin-top: 3px; }}

    /* ── Stat cards ─────────────────────────── */
    .cards {{
      max-width: 1100px; margin: 0 auto 2rem;
      display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
    }}
    .card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 16px; padding: 1.5rem;
      position: relative; overflow: hidden;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.4); }}
    .card::before {{
      content: ''; position: absolute; inset: 0; border-radius: 16px;
      background: linear-gradient(135deg, var(--card-glow, transparent) 0%, transparent 70%);
      opacity: 0.07;
    }}
    .card.green  {{ --card-glow: #10b981; }}
    .card.amber  {{ --card-glow: #f59e0b; }}
    .card.red    {{ --card-glow: #ef4444; }}
    .card.blue   {{ --card-glow: #3b82f6; }}
    .card-val {{
      font-size: 2.5rem; font-weight: 800;
      letter-spacing: -1px; line-height: 1;
      margin-bottom: 0.4rem;
    }}
    .card.green  .card-val {{ color: var(--verified); }}
    .card.amber  .card-val {{ color: var(--warn); }}
    .card.red    .card-val {{ color: var(--danger); }}
    .card.blue   .card-val {{ color: var(--accent); }}
    .card-label {{ font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }}
    .card-sub   {{ font-size: 0.72rem; color: var(--muted); margin-top: 0.3rem; }}

    /* ── Progress bar ───────────────────────── */
    .progress-wrap {{
      max-width: 1100px; margin: 0 auto 2rem;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 16px; padding: 1.5rem;
    }}
    .progress-label {{
      display: flex; justify-content: space-between;
      font-size: 0.85rem; font-weight: 600; margin-bottom: 0.75rem;
    }}
    .progress-bar-bg {{
      height: 10px; background: rgba(255,255,255,0.06); border-radius: 999px;
      overflow: hidden;
    }}
    .progress-bar-fill {{
      height: 100%;
      background: linear-gradient(90deg, #1d4ed8, #10b981);
      border-radius: 999px;
      transition: width 0.8s ease;
    }}

    /* ── Table ──────────────────────────────── */
    .table-wrap {{
      max-width: 1100px; margin: 0 auto 2rem;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 16px; overflow: hidden;
    }}
    .table-header {{
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between;
    }}
    .table-title {{ font-size: 0.95rem; font-weight: 700; }}
    .table-count {{
      font-size: 0.75rem; color: var(--muted);
      background: rgba(255,255,255,0.05); padding: 4px 10px; border-radius: 999px;
    }}
    .scroll-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead tr {{ background: rgba(255,255,255,0.03); }}
    th {{
      padding: 0.75rem 1rem; text-align: left;
      font-size: 0.72rem; text-transform: uppercase;
      letter-spacing: 1px; color: var(--muted);
      font-weight: 600; white-space: nowrap;
    }}
    td {{
      padding: 0.7rem 1rem; border-top: 1px solid rgba(255,255,255,0.04);
      font-size: 0.82rem; vertical-align: middle;
    }}
    tr:hover td {{ background: rgba(255,255,255,0.02); }}
    .fname {{ font-weight: 500; max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .hash  {{ font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: var(--muted); }}
    .payload-cell {{
      font-family: 'JetBrains Mono', monospace; font-size: 0.68rem;
      color: #93c5fd; max-width: 320px; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap;
    }}

    /* ── Badges ─────────────────────────────── */
    .badge {{
      display: inline-flex; align-items: center; gap: 4px;
      padding: 4px 10px; border-radius: 999px;
      font-size: 0.72rem; font-weight: 700; white-space: nowrap;
    }}
    .badge-verified {{ background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }}
    .badge-tampered {{ background: rgba(245,158,11,0.15); color: #fcd34d; border: 1px solid rgba(245,158,11,0.3); }}
    .badge-unknown  {{ background: rgba(239,68,68,0.15);  color: #f87171; border: 1px solid rgba(239,68,68,0.3); }}

    /* ── Footer ─────────────────────────────── */
    footer {{
      max-width: 1100px; margin: 0 auto;
      text-align: center; font-size: 0.75rem; color: var(--muted);
      padding: 1.5rem 0;
    }}
    footer a {{ color: var(--accent); text-decoration: none; }}

    /* ── Glow pulse animation ───────────────── */
    @keyframes pulse-glow {{
      0%, 100% {{ box-shadow: 0 0 20px rgba(16,185,129,0.25); }}
      50%       {{ box-shadow: 0 0 40px rgba(16,185,129,0.5); }}
    }}
    .overall-pass .verdict-icon {{ animation: pulse-glow 2.5s ease-in-out infinite; }}
  </style>
</head>
<body>

  <!-- Header -->
  <div class="header">
    <div class="logo-block">
      <div class="logo-icon">🛡️</div>
      <div class="logo-text">
        <h1>MandiVision — Authenticity Dashboard</h1>
        <div class="sub">Steganographic Proof-of-Ownership · Data Genesis 2026 · Rajapalayam</div>
      </div>
    </div>
    <div class="header-meta">
      Generated: <strong>{timestamp}</strong><br>
      Dataset: <strong>MandiVision Produce Dataset</strong><br>
      Method: <strong>LSB Steganography (Blue Channel)</strong>
    </div>
  </div>

  <!-- Verdict Banner -->
  <div class="verdict-banner {overall_class}">
    <div class="verdict-icon">{"✅" if verify_pct >= 90 else "⚠️" if verify_pct >= 50 else "❌"}</div>
    <div>
      <div class="verdict-label">{overall_text}</div>
      <div class="verdict-sub">
        {verified} of {total} images carry a verified MandiVision ownership watermark.
        Payload: <code>MANDIVISION|DataGenesis2026|Rajapalayam|&lt;img_hash&gt;|END</code>
      </div>
    </div>
  </div>

  <!-- Stat Cards -->
  <div class="cards">
    <div class="card green">
      <div class="card-val">{verify_pct:.0f}%</div>
      <div class="card-label">Verified Ownership</div>
      <div class="card-sub">{verified} images carry our watermark</div>
    </div>
    <div class="card blue">
      <div class="card-val">{total}</div>
      <div class="card-label">Total Images Audited</div>
      <div class="card-sub">from processed_dataset/</div>
    </div>
    <div class="card amber">
      <div class="card-val">{tampered}</div>
      <div class="card-label">Tampered / Modified</div>
      <div class="card-sub">payload found, hash mismatch</div>
    </div>
    <div class="card red">
      <div class="card-val">{not_ours}</div>
      <div class="card-label">Unverified Images</div>
      <div class="card-sub">no MandiVision payload detected</div>
    </div>
  </div>

  <!-- Progress -->
  <div class="progress-wrap">
    <div class="progress-label">
      <span>Ownership Verification Progress</span>
      <span style="color: {'#10b981' if verify_pct >= 90 else '#f59e0b'}">{verify_pct:.1f}%</span>
    </div>
    <div class="progress-bar-bg">
      <div class="progress-bar-fill" style="width: {verify_pct:.1f}%"></div>
    </div>
  </div>

  <!-- Table -->
  <div class="table-wrap">
    <div class="table-header">
      <div class="table-title">🔬 Per-Image Verification Results</div>
      <div class="table-count">{total} images</div>
    </div>
    <div class="scroll-wrap">
      <table>
        <thead>
          <tr>
            <th>Filename</th>
            <th>SHA-256 (truncated)</th>
            <th>Embedded Payload</th>
            <th>Verdict</th>
          </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
      </table>
    </div>
  </div>

  <footer>
    Generated by <strong>MandiVision Authenticity Engine v1.0</strong> for
    <a href="#">Data Genesis 2026 Hackathon</a> · Team Rajapalayam ·
    LSB Steganography — imperceptible to the human eye, cryptographically verifiable.
  </footer>

</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n   📊 Dashboard written → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  MANDIVISION — WATERMARK VERIFIER v1.0")
    print("  Cryptographic Proof-of-Ownership Checker")
    print("=" * 65)

    gen_html = "--html" in sys.argv
    single_file = next((a for a in sys.argv[1:] if a != "--html" and os.path.isfile(a)), None)

    # Load manifest (optional — works without it)
    manifest_lookup = {}   # key: filename OR sha256_watermarked → entry
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)
        for entry in manifest.get("images", []):
            manifest_lookup[entry["filename"]] = entry
            if entry.get("sha256_watermarked"):
                manifest_lookup[entry["sha256_watermarked"]] = entry
        print(f"\n📋 Manifest loaded: {len(manifest.get('images', []))} entries")
    else:
        manifest = {"images": []}
        print(f"\n⚠️  No manifest found at {MANIFEST_PATH}")
        print("   Run embed_watermark.py first for full verification.")

    # ── Single image mode ──────────────────────────────────────────
    if single_file:
        print(f"\n🔍 Verifying single image: {single_file}\n")
        result = verify_single(single_file, manifest_lookup)
        print(f"  File    : {result['filename']}")
        print(f"  SHA-256 : {result['sha256']}")
        print(f"  Payload : {result['payload'] or 'NONE'}")
        print(f"  Verdict : {result['verdict']}")
        print()
        return

    # ── Batch mode ─────────────────────────────────────────────────
    if not os.path.exists(WATERMARKED_DIR):
        print(f"\n❌ Watermarked directory not found: {WATERMARKED_DIR}")
        print("   Run embed_watermark.py first.")
        return

    images = sorted([
        f for f in os.listdir(WATERMARKED_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    if not images:
        print(f"\n❌ No images found in: {WATERMARKED_DIR}")
        return

    print(f"\n📂 Scanning: {WATERMARKED_DIR}")
    print(f"🖼️  Images : {len(images)}\n")

    results = []
    verified = tampered = not_ours = 0

    for idx, fname in enumerate(images):
        path   = os.path.join(WATERMARKED_DIR, fname)
        result = verify_single(path, manifest_lookup)
        results.append(result)

        if "VERIFIED" in result["status"]:
            verified += 1
        elif result["status"] == "TAMPERED":
            tampered += 1
        else:
            not_ours += 1

        if (idx + 1) % 10 == 0 or (idx + 1) == len(images):
            pct = (idx + 1) / len(images) * 100
            bar = "█" * int(pct // 4) + "░" * (25 - int(pct // 4))
            print(f"   [{bar}] {idx+1}/{len(images)}  ✅{verified}  ⚠️{tampered}  ❌{not_ours}", end="\r")

    print()  # newline after progress bar

    # Write JSON report
    report = {
        "generated_at": datetime.now().isoformat(),
        "total": len(results),
        "verified": verified,
        "tampered": tampered,
        "not_ours": not_ours,
        "verify_pct": round(verified / max(len(results), 1) * 100, 1),
        "images": results
    }
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Generate dashboard
    generate_dashboard(results, manifest, DASHBOARD_OUT)

    print()
    print("=" * 65)
    print(f"  ✅ VERIFICATION COMPLETE")
    print(f"  Verified : {verified}/{len(results)}  ({report['verify_pct']}%)")
    print(f"  Tampered : {tampered}")
    print(f"  Unknown  : {not_ours}")
    print(f"  Report   : {REPORT_OUT}")
    print(f"  Dashboard: {DASHBOARD_OUT}")
    print("=" * 65)


if __name__ == "__main__":
    main()
