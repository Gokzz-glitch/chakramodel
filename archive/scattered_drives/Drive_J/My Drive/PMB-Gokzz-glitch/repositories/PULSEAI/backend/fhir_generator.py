import uuid
from datetime import datetime
import json
from typing import Optional, List

def generate_fhir_diagnostic_report(patient_id: str, classification: str, confidence: float, explainability_map: Optional[dict] = None) -> dict:
    """
    Creates an HL7 FHIR R4 Compliant DiagnosticReport resource.
    Specifically targeting the ABDM Sandbox requirements, incorporating a
    Grad-CAM AI Explainability observation to eliminate the "Black-Box" penalty.
    """
    now = datetime.utcnow().isoformat() + "Z"
    report_id = str(uuid.uuid4())

    fhir_report = {
        "resourceType": "DiagnosticReport",
        "id": report_id,
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "LP29708-2",
                        "display": "Cardiology"
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "85994008",
                    "display": "Electrocardiogram"
                }
            ],
            "text": "1-Lead Ambulatory ECG Continuous Monitor with TransMixer AI"
        },
        "subject": {
            "reference": f"Patient/{patient_id}"
        },
        "effectiveDateTime": now,
        "issued": now,
        "performer": [
            {
                "reference": "Device/PulseAI-Federated-TransMixer",
                "display": "PulseAI Edge AI Triage Engine"
            }
        ],
        "conclusion": classification,
        "conclusionCode": [
            {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "164889003" if "AFib" in classification else "426177001",
                        "display": classification
                    }
                ]
            }
        ],
        # Appending Model Explainability directly into the FHIR structure as metadata
        "extension": [
            {
                "url": "http://pulseai.health/fhir/extension/confidence",
                "valueDecimal": confidence
            }
        ],
        "presentedForm": [
            {
                "contentType": "application/json",
                "title": "Raw ECG Waveform Telemetry",
                "url": f"https://sandbox.abdm.gov.in/ecg/archive/{report_id}-waveform.json"
            }
        ]
    }

    if explainability_map:
        # Embedding the Grad-CAM saliency details for clinician review
        # The doctor sees EXACTLY why the AI flagged this segment.
        ext_list = fhir_report.get("extension", [])
        if isinstance(ext_list, list):
            ext_list.append({
                "url": "http://pulseai.health/fhir/extension/gradcam-attention",
                "valueString": json.dumps(explainability_map)
            })
            fhir_report["extension"] = ext_list

    return fhir_report
