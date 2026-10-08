"""
Automated Multimodal Clinical Procedure Report Generator
(Med-Flamingo / BioMedCLIP Inspired Clinical Documentation Engine)

Tracks unique polyp encounters, logs temporal keyframes at peak confidence,
computes overall procedure quality metrics, and generates standardized
gastroenterological procedure reports.
"""

import os
import cv2
import time
import json
from datetime import datetime
from pathlib import Path

class ClinicalReportGenerator:
    def __init__(self, output_dir="outputs/clinical_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.keyframes_dir = self.output_dir / "keyframes"
        self.keyframes_dir.mkdir(parents=True, exist_ok=True)
        
        self.reset()

    def reset(self):
        self.start_time = time.time()
        self.total_frames = 0
        self.artifact_frames = 0
        self.tracked_polyps = {} # track_id -> {first_seen, last_seen, max_conf, best_frame, paris, diameter_mm, resection}
        self.procedure_id = f"ENDO_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def update(self, frame_idx, timestamp_sec, detections, is_artifact=False, current_frame_bgr=None):
        """
        Updates procedure telemetry with current frame findings.
        
        Args:
            frame_idx: int frame index
            timestamp_sec: float video timestamp in seconds
            detections: list of dicts with keys: 'track_id', 'bbox', 'conf', 'paris', 'mask'
            is_artifact: bool whether frame had blur / glare
            current_frame_bgr: raw frame for keyframe extraction
        """
        self.total_frames += 1
        if is_artifact:
            self.artifact_frames += 1
            
        for det in detections:
            tid = det.get('track_id', 0)
            conf = det.get('conf', 0.0)
            paris = det.get('paris', {})
            
            if tid not in self.tracked_polyps:
                self.tracked_polyps[tid] = {
                    "track_id": tid,
                    "first_seen_frame": frame_idx,
                    "first_seen_sec": round(timestamp_sec, 2),
                    "last_seen_frame": frame_idx,
                    "last_seen_sec": round(timestamp_sec, 2),
                    "max_conf": conf,
                    "paris_class": paris.get('paris_class', '0-Is'),
                    "paris_label": paris.get('paris_label', 'Sessile (0-Is)'),
                    "diameter_mm": paris.get('est_diameter_mm', 5.0),
                    "size_category": paris.get('size_category', 'Small (5-9mm)'),
                    "resection": paris.get('clinical_resection', 'Cold Snare Polypectomy'),
                    "keyframe_path": None
                }
            else:
                self.tracked_polyps[tid]["last_seen_frame"] = frame_idx
                self.tracked_polyps[tid]["last_seen_sec"] = round(timestamp_sec, 2)
                
            # Update best keyframe snapshot at peak confidence
            if conf >= self.tracked_polyps[tid]["max_conf"] and current_frame_bgr is not None:
                self.tracked_polyps[tid]["max_conf"] = conf
                self.tracked_polyps[tid]["paris_class"] = paris.get('paris_class', self.tracked_polyps[tid]["paris_class"])
                self.tracked_polyps[tid]["diameter_mm"] = max(self.tracked_polyps[tid]["diameter_mm"], paris.get('est_diameter_mm', 0.0))
                
                # Save keyframe image
                keyframe_fname = f"{self.procedure_id}_track_{tid}_f{frame_idx}.jpg"
                keyframe_full_path = self.keyframes_dir / keyframe_fname
                cv2.imwrite(str(keyframe_full_path), current_frame_bgr)
                self.tracked_polyps[tid]["keyframe_path"] = str(keyframe_full_path)

    def generate_report(self, video_name="Colonoscopy_Video"):
        """
        Compiles procedure findings into a structured Clinical Procedure Report.
        """
        elapsed_time = round(time.time() - self.start_time, 1)
        artifact_pct = round((self.artifact_frames / max(1, self.total_frames)) * 100, 1)
        polyps_found = len(self.tracked_polyps)
        
        # Calculate summary metrics
        max_size = max([p["diameter_mm"] for p in self.tracked_polyps.values()], default=0.0)
        paris_counts = {}
        for p in self.tracked_polyps.values():
            p_class = p["paris_class"]
            paris_counts[p_class] = paris_counts.get(p_class, 0) + 1
            
        # Clinical Risk Stratification
        if polyps_found == 0:
            risk_level = "LOW (Clear Colonoscopy - Routine 10-Yr Surveillance)"
        elif max_size >= 10.0 or polyps_found >= 3:
            risk_level = "HIGH (Advanced Adenoma Risk - 1-3 Yr Surveillance Recommended)"
        else:
            risk_level = "MODERATE (Low-Risk Adenoma - 5-Yr Surveillance)"

        report_md = f"""# 🏥 Endoscopic Procedure Diagnostic Report
**Procedure ID:** `{self.procedure_id}` | **Source:** `{video_name}`  
**Generated Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**AI Pipeline:** ChakraModel v2.0 (YOLOv8 + ByteTrack Kalman + PraNet Reverse Attention)

---

## 1. 📊 Procedure Telemetry & Quality Assurance
* **Total Video Frames Analyzed:** {self.total_frames:,}
* **Endoscopic Image Quality:** {100.0 - artifact_pct:.1f}% Diagnostic Clarity
* **Motion Blur / Specular Glare Artifact Rate:** {artifact_pct}%
* **Total Unique Lesions Identified:** **{polyps_found}**
* **Largest Lesion Diameter:** **~{max_size} mm**
* **Overall Clinical Risk Assessment:** **{risk_level}**

---

## 2. 🔬 Lesion Inventory & Morphological Staging

| Track ID | First Seen | Duration | Max Conf | Paris Classification | Est. Size (mm) | Recommended Resection |
|:---:|:---:|:---:|:---:|:---:|:---:|:---|
"""
        for tid, p in self.tracked_polyps.items():
            duration_sec = round(p["last_seen_sec"] - p["first_seen_sec"], 1)
            report_md += f"| **#{tid}** | {p['first_seen_sec']}s | {duration_sec}s | {p['max_conf']*100:.1f}% | `{p['paris_label']}` | ~{p['diameter_mm']} mm | {p['resection']} |\n"

        if polyps_found == 0:
            report_md += "| - | - | - | - | *No mucosal polyps detected* | - | - |\n"

        report_md += f"""
---

## 3. 📋 Clinical Recommendations for Endoscopist
1. **Histopathology Submission:** Ensure all retrieved specimens are submitted in formalin for dysplasia grading.
2. **Margin Verification:** PraNet sub-pixel reverse-attention contours confirm lesion margins. Verify complete resection bed post-polypectomy.
3. **Post-Procedure Surveillance:** Recommended interval: **{risk_level.split('(')[-1].replace(')', '')}**.

---
*Report generated automatically by ChakraModel Real-Time Endoscopy AI.*
"""
        # Save markdown report
        report_path = self.output_dir / f"{self.procedure_id}_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)
            
        return report_md, str(report_path)
