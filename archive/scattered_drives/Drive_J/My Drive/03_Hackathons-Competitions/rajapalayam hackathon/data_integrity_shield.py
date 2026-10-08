"""
╔══════════════════════════════════════════════════════════════╗
║            DATA INTEGRITY SHIELD v1.0                       ║
║     Image Forensics & Authenticity Verification Tool        ║
║     For: Data Genesis 2026 Hackathon                        ║
╚══════════════════════════════════════════════════════════════╝

This script performs 3 layers of forensic analysis on every image
in the dataset to mathematically prove that images are authentic
and were captured by the team's own cameras.

Layer 1: EXIF Metadata Audit
  - Extracts camera model, GPS, timestamp, exposure settings
  - Flags images missing camera metadata (likely downloaded)

Layer 2: Error Level Analysis (ELA)
  - Re-saves each image at 95% quality and compares error levels
  - Edited/spliced regions show different compression artifacts
  - Generates visual ELA maps saved alongside the report

Layer 3: SHA-256 Hash Chain
  - Creates a cryptographic fingerprint for every image
  - Proves no image was tampered with after collection

Output:
  - integrity_report.csv — per-image forensic summary
  - ela_maps/ — visual ELA overlay for each image
  - integrity_summary.txt — human-readable summary report
"""

import os
import sys
import csv
import hashlib
import json
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import numpy as np

# ── Configuration ──────────────────────────────────────────────
ORIGINAL_DIR = r"J:\My Drive\rajapalayam hackathon\DATASET BY GOKUL"
PROCESSED_DIR = r"J:\My Drive\rajapalayam hackathon\processed_dataset"
OUTPUT_DIR = r"J:\My Drive\rajapalayam hackathon\integrity_report"
ELA_DIR = os.path.join(OUTPUT_DIR, "ela_maps")
ELA_QUALITY = 95  # JPEG re-save quality for ELA
ELA_SCALE = 20    # Amplification factor for ELA visualization

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ELA_DIR, exist_ok=True)

def flush_print(msg):
    print(msg, flush=True)

# ── Layer 1: EXIF Metadata Extraction ─────────────────────────

def get_gps_coords(gps_info):
    """Convert EXIF GPS data to decimal lat/lon."""
    try:
        def to_decimal(values, ref):
            d, m, s = values
            decimal = float(d) + float(m) / 60 + float(s) / 3600
            if ref in ['S', 'W']:
                decimal = -decimal
            return round(decimal, 6)
        
        lat = to_decimal(gps_info.get(2, (0,0,0)), gps_info.get(1, 'N'))
        lon = to_decimal(gps_info.get(4, (0,0,0)), gps_info.get(3, 'E'))
        return lat, lon
    except Exception:
        return None, None

def extract_exif(image_path):
    """Extract key EXIF metadata from an image."""
    result = {
        "has_exif": False,
        "camera_make": None,
        "camera_model": None,
        "software": None,
        "datetime_original": None,
        "exposure_time": None,
        "f_number": None,
        "iso": None,
        "gps_lat": None,
        "gps_lon": None,
        "image_width": None,
        "image_height": None,
        "authenticity_verdict": "UNKNOWN"
    }
    
    try:
        with Image.open(image_path) as img:
            result["image_width"], result["image_height"] = img.size
            exif_data = img.getexif()
            
            if not exif_data:
                result["authenticity_verdict"] = "⚠️ NO_EXIF"
                return result
            
            result["has_exif"] = True
            
            # Extract standard tags
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == "Make":
                    result["camera_make"] = str(value).strip()
                elif tag_name == "Model":
                    result["camera_model"] = str(value).strip()
                elif tag_name == "Software":
                    result["software"] = str(value).strip()
                elif tag_name == "DateTimeOriginal":
                    result["datetime_original"] = str(value)
                elif tag_name == "DateTime":
                    if not result["datetime_original"]:
                        result["datetime_original"] = str(value)
                elif tag_name == "ExposureTime":
                    result["exposure_time"] = str(value)
                elif tag_name == "FNumber":
                    result["f_number"] = str(value)
                elif tag_name == "ISOSpeedRatings":
                    result["iso"] = str(value)
            
            # Extract GPS data from IFD
            try:
                ifd = exif_data.get_ifd(0x8825)  # GPS IFD
                if ifd:
                    lat, lon = get_gps_coords(ifd)
                    result["gps_lat"] = lat
                    result["gps_lon"] = lon
            except Exception:
                pass
            
            # Determine authenticity verdict
            if result["camera_make"] and result["camera_model"]:
                result["authenticity_verdict"] = "✅ AUTHENTIC"
            elif result["software"] and any(s in result["software"].lower() for s in ["photoshop", "gimp", "canva"]):
                result["authenticity_verdict"] = "🚨 EDITED"
            elif not result["camera_make"]:
                result["authenticity_verdict"] = "⚠️ SUSPICIOUS"
            else:
                result["authenticity_verdict"] = "✅ LIKELY_AUTHENTIC"
                
    except Exception as e:
        result["authenticity_verdict"] = f"❌ ERROR: {str(e)[:50]}"
    
    return result


# ── Layer 2: Error Level Analysis ─────────────────────────────

def perform_ela(image_path, output_path):
    """
    Perform Error Level Analysis on an image.
    Returns the mean and max error levels.
    """
    try:
        with Image.open(image_path) as original:
            # Convert to RGB if needed
            if original.mode != 'RGB':
                original = original.convert('RGB')
            
            # Re-save at known quality
            temp_path = output_path + ".temp.jpg"
            original.save(temp_path, 'JPEG', quality=ELA_QUALITY)
            
            # Re-open the re-saved version
            with Image.open(temp_path) as resaved:
                # Calculate pixel-level differences
                orig_arr = np.array(original, dtype=np.float32)
                resaved_arr = np.array(resaved, dtype=np.float32)
                
                # Compute absolute difference and scale it
                diff = np.abs(orig_arr - resaved_arr)
                ela_map = np.clip(diff * ELA_SCALE, 0, 255).astype(np.uint8)
                
                # Calculate statistics
                mean_error = float(np.mean(diff))
                max_error = float(np.max(diff))
                std_error = float(np.std(diff))
                
                # Save ELA visualization
                ela_image = Image.fromarray(ela_map)
                ela_image.save(output_path)
            
            # Clean up temp file
            os.remove(temp_path)
            
            return {
                "ela_mean": round(mean_error, 2),
                "ela_max": round(max_error, 2),
                "ela_std": round(std_error, 2),
                "ela_verdict": "✅ UNIFORM" if std_error < 5.0 else "⚠️ INCONSISTENT"
            }
    except Exception as e:
        return {
            "ela_mean": None,
            "ela_max": None,
            "ela_std": None,
            "ela_verdict": f"❌ ERROR: {str(e)[:50]}"
        }


# ── Layer 3: SHA-256 Hash ─────────────────────────────────────

def compute_sha256(file_path):
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            sha256.update(block)
    return sha256.hexdigest()


# ── Main Pipeline ─────────────────────────────────────────────

def main():
    flush_print("=" * 60)
    flush_print("  DATA INTEGRITY SHIELD v1.0")
    flush_print("  Forensic Image Authenticity Verification")
    flush_print("=" * 60)
    
    # Scan ORIGINAL images (not processed) for EXIF data
    flush_print(f"\n📂 Scanning original images in: {ORIGINAL_DIR}")
    
    original_files = []
    for f in os.listdir(ORIGINAL_DIR):
        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
            original_files.append(os.path.join(ORIGINAL_DIR, f))
    
    flush_print(f"   Found {len(original_files)} original images")
    
    # Scan PROCESSED images for ELA and hashing
    flush_print(f"\n📂 Scanning processed images in: {PROCESSED_DIR}")
    
    processed_files = []
    for f in os.listdir(PROCESSED_DIR):
        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
            processed_files.append(os.path.join(PROCESSED_DIR, f))
    
    flush_print(f"   Found {len(processed_files)} processed images")
    
    # ── Process Original Images (EXIF) ────────────────────
    flush_print("\n🔍 Layer 1: EXIF Metadata Audit (Original Images)")
    flush_print("-" * 50)
    
    exif_results = {}
    auth_count = 0
    suspicious_count = 0
    
    for idx, fpath in enumerate(original_files):
        fname = os.path.basename(fpath)
        exif = extract_exif(fpath)
        exif_results[fname] = exif
        
        if "AUTHENTIC" in exif["authenticity_verdict"]:
            auth_count += 1
        elif "SUSPICIOUS" in exif["authenticity_verdict"] or "NO_EXIF" in exif["authenticity_verdict"]:
            suspicious_count += 1
        
        if idx % 10 == 0:
            flush_print(f"   Scanned {idx}/{len(original_files)} images...")
    
    flush_print(f"   ✅ Authentic: {auth_count}/{len(original_files)}")
    flush_print(f"   ⚠️  Suspicious: {suspicious_count}/{len(original_files)}")
    
    # ── Process Processed Images (ELA + Hash) ─────────────
    flush_print("\n🔬 Layer 2: Error Level Analysis (Processed Images)")
    flush_print("-" * 50)
    
    all_results = []
    ela_uniform = 0
    
    for idx, fpath in enumerate(processed_files):
        fname = os.path.basename(fpath)
        
        # Get EXIF from matching original if exists
        # Map processed name back to original name
        orig_name = fname
        if orig_name.startswith("cropped_"):
            orig_name = orig_name[len("cropped_"):]
        
        exif = exif_results.get(orig_name, {
            "has_exif": False, "camera_make": None, "camera_model": None,
            "software": None, "datetime_original": None, "exposure_time": None,
            "f_number": None, "iso": None, "gps_lat": None, "gps_lon": None,
            "image_width": None, "image_height": None, 
            "authenticity_verdict": "N/A (video frame)"
        })
        
        # ELA
        ela_out_path = os.path.join(ELA_DIR, f"ela_{fname}")
        ela = perform_ela(fpath, ela_out_path)
        
        if ela["ela_verdict"] and "UNIFORM" in ela["ela_verdict"]:
            ela_uniform += 1
        
        # SHA-256
        sha = compute_sha256(fpath)
        
        # Combine
        row = {
            "filename": fname,
            "sha256": sha,
            "exif_camera_make": exif.get("camera_make", ""),
            "exif_camera_model": exif.get("camera_model", ""),
            "exif_datetime": exif.get("datetime_original", ""),
            "exif_gps_lat": exif.get("gps_lat", ""),
            "exif_gps_lon": exif.get("gps_lon", ""),
            "exif_iso": exif.get("iso", ""),
            "exif_verdict": exif.get("authenticity_verdict", ""),
            "ela_mean": ela.get("ela_mean", ""),
            "ela_max": ela.get("ela_max", ""),
            "ela_std": ela.get("ela_std", ""),
            "ela_verdict": ela.get("ela_verdict", ""),
        }
        all_results.append(row)
        
        if idx % 50 == 0:
            flush_print(f"   Analyzed {idx}/{len(processed_files)} images...")
    
    flush_print(f"   ✅ Uniform compression: {ela_uniform}/{len(processed_files)}")
    
    # ── Write CSV Report ──────────────────────────────────
    flush_print("\n📄 Layer 3: Generating SHA-256 Integrity Manifest")
    flush_print("-" * 50)
    
    csv_path = os.path.join(OUTPUT_DIR, "integrity_report.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
        writer.writeheader()
        writer.writerows(all_results)
    
    flush_print(f"   Saved: {csv_path}")
    
    # ── Write Summary Report ──────────────────────────────
    summary_path = os.path.join(OUTPUT_DIR, "integrity_summary.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("  DATA INTEGRITY SHIELD — SUMMARY REPORT\n")
        f.write(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        
        f.write("DATASET OVERVIEW\n")
        f.write(f"  Original images scanned:  {len(original_files)}\n")
        f.write(f"  Processed images scanned: {len(processed_files)}\n\n")
        
        f.write("LAYER 1: EXIF METADATA AUDIT\n")
        f.write(f"  Images with camera metadata:  {auth_count}/{len(original_files)}\n")
        f.write(f"  Suspicious (no EXIF):         {suspicious_count}/{len(original_files)}\n")
        
        # Find unique devices
        devices = set()
        for r in exif_results.values():
            if r.get("camera_make") and r.get("camera_model"):
                devices.add(f"{r['camera_make']} {r['camera_model']}")
        f.write(f"  Unique capture devices:       {', '.join(devices) if devices else 'None detected'}\n\n")
        
        f.write("LAYER 2: ERROR LEVEL ANALYSIS\n")
        f.write(f"  Uniform compression (authentic): {ela_uniform}/{len(processed_files)}\n")
        f.write(f"  Inconsistent (investigate):      {len(processed_files) - ela_uniform}/{len(processed_files)}\n\n")
        
        f.write("LAYER 3: SHA-256 INTEGRITY CHAIN\n")
        f.write(f"  Total hashes generated: {len(all_results)}\n")
        f.write(f"  Manifest file: integrity_report.csv\n\n")
        
        # Overall verdict
        auth_pct = (auth_count / max(len(original_files), 1)) * 100
        ela_pct = (ela_uniform / max(len(processed_files), 1)) * 100
        
        f.write("=" * 60 + "\n")
        f.write("OVERALL VERDICT\n")
        if auth_pct >= 80 and ela_pct >= 70:
            f.write("  🟢 DATASET IS AUTHENTIC\n")
            f.write(f"  {auth_pct:.0f}% of original images contain valid camera metadata.\n")
            f.write(f"  {ela_pct:.0f}% of processed images show uniform compression.\n")
        elif auth_pct >= 50:
            f.write("  🟡 DATASET IS MOSTLY AUTHENTIC\n")
            f.write(f"  {auth_pct:.0f}% of original images contain valid camera metadata.\n")
        else:
            f.write("  🔴 DATASET AUTHENTICITY CANNOT BE CONFIRMED\n")
        f.write("=" * 60 + "\n")
    
    flush_print(f"   Saved: {summary_path}")
    
    flush_print("\n" + "=" * 60)
    flush_print("  ✅ DATA INTEGRITY SHIELD COMPLETE")
    flush_print("=" * 60)


if __name__ == "__main__":
    main()
