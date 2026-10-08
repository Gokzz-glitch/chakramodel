import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any, cast, List

import numpy as np  # type: ignore
from scipy.signal import find_peaks  # type: ignore

try:
    from tensorflow import keras  # type: ignore
except Exception:  # pragma: no cover
    keras = None

logger = logging.getLogger(__name__)

FS = 500


class ArrhythmiaEngine:
    """Production-safe ECG inference with ML-first and deterministic fallback."""

    def __init__(self) -> None:
        self.model_path = Path(os.getenv("MODEL_PATH", "hctg_net_model.h5"))
        self.thresholds_path = Path(os.getenv("MODEL_THRESHOLDS_PATH", "model_thresholds.json"))
        self.model = None
        self.model_version = "heuristic-v2"
        self.labels = ["Normal Sinus Rhythm", "Atrial Fibrillation (AFib)", "Other Arrhythmia"]
        self.binary_decision_threshold = 0.50
        # Allow high-confidence ML calls to survive consensus gating by default.
        self.strong_ml_override_confidence = self._env_float("PULSEAI_STRONG_ML_OVERRIDE_CONF", 0.78)
        self.enable_heuristic_safety_override = self._env_bool("PULSEAI_ENABLE_HEURISTIC_SAFETY", False)
        self.min_arrhythmia_confidence = self._env_float("PULSEAI_ARRHYTHMIA_MIN_CONF", 0.65)
        self.max_normal_prob_for_arrhythmia = self._env_float("PULSEAI_MAX_NORMAL_PROB_FOR_ARR", 0.65)
        self.require_good_quality_for_non_critical = self._env_bool("PULSEAI_REQUIRE_GOOD_QUALITY", False)
        self.review_uncertainty_threshold = self._env_float("PULSEAI_REVIEW_UNCERTAINTY_THRESHOLD", 0.50)
        self.high_uncertainty_threshold = self._env_float("PULSEAI_HIGH_UNCERTAINTY_THRESHOLD", 0.78)
        self.no_guess_uncertainty_threshold = self._env_float("PULSEAI_NO_GUESS_UNCERTAINTY_THRESHOLD", 0.88)
        self.critical_arrhythmia_labels = {
            "ventricular fibrillation (vf)",
            "ventricular tachycardia (vt)",
            "atrial fibrillation (afib)",
        }
        self._load_thresholds_if_available()
        self.binary_decision_threshold = self._env_float("PULSEAI_BINARY_THRESHOLD", self.binary_decision_threshold)
        self._load_model_if_available()

    @staticmethod
    def _env_float(key: str, default: float) -> float:
        raw = os.getenv(key)
        if raw is None:
            return default
        try:
            return float(raw)
        except Exception:
            return default

    @staticmethod
    def _env_bool(key: str, default: bool) -> bool:
        raw = os.getenv(key)
        if raw is None:
            return default
        return raw.strip().lower() not in ("0", "false", "no")

    def _apply_decision_policy(self, out: Dict) -> Dict:
        """Apply tunable post-classification policy to control FP/FN tradeoff."""
        result = dict(out)
        cls = str(result.get("classification", "")).strip()
        cls_l = cls.lower()
        conf = float(result.get("confidence", 0.0) or 0.0)
        probs = result.get("probabilities") if isinstance(result.get("probabilities"), dict) else {}
        normal_prob = float(probs.get("normal", 0.0) or 0.0) if isinstance(probs, dict) else 0.0
        rr_cv = result.get("rr_cv")
        hr = result.get("heart_rate_bpm")
        quality = str(result.get("signal_quality", "fair")).lower()
        is_critical = cls_l in self.critical_arrhythmia_labels
        is_other_non_critical = ("other arrhythmia" in cls_l) and (not is_critical)

        if bool(result.get("is_arrhythmia", False)) and not is_critical:
            low_conf = conf < self.min_arrhythmia_confidence
            high_normal_prob = normal_prob > self.max_normal_prob_for_arrhythmia
            low_quality = self.require_good_quality_for_non_critical and quality != "good"

            # Targeted guardrail for broad "Other Arrhythmia" calls:
            # if physiologic rhythm looks near-normal and confidence is only moderate,
            # downgrade to review class to reduce false-positive burden.
            weak_other_support = False
            if is_other_non_critical:
                rr_near_normal = isinstance(rr_cv, (int, float)) and float(rr_cv) < 0.17
                hr_near_normal = isinstance(hr, (int, float)) and 55.0 <= float(hr) <= 120.0
                moderate_conf = conf < 0.74
                weak_other_support = rr_near_normal and hr_near_normal and (moderate_conf or normal_prob >= 0.42)

            if low_conf or high_normal_prob or low_quality or weak_other_support:
                result["is_arrhythmia"] = False
                result["classification"] = "Subtle Rhythm Irregularity (Review)"
                result["model_used"] = f"{result.get('model_used', self.model_version)}+policy-gate"

        return result

    def _attach_uncertainty(self, out: Dict) -> Dict:
        """Attach calibrated uncertainty metadata used by clinical review flow."""
        result = dict(out)
        conf = float(result.get("confidence", 0.0) or 0.0)
        probs = result.get("probabilities") if isinstance(result.get("probabilities"), dict) else {}
        values: List[float] = []
        if isinstance(probs, dict):
            for k in ("normal", "afib", "other"):
                if k in probs:
                    values.append(float(probs.get(k, 0.0) or 0.0))

        entropy_component = 0.0
        if values:
            arr = np.asarray(values, dtype=np.float64)
            arr = np.clip(arr, 1e-8, 1.0)
            arr = arr / max(float(np.sum(arr)), 1e-8)
            entropy = -float(np.sum(arr * np.log(arr)))
            max_entropy = float(np.log(len(arr))) if len(arr) > 1 else 1.0
            entropy_component = entropy / max(max_entropy, 1e-8)

        uncertainty = max(1.0 - conf, entropy_component)
        cls_l = str(result.get("classification", "")).strip().lower()
        review_like = (
            "review" in cls_l
            or "poor signal" in cls_l
            or "insufficient" in cls_l
            or bool(result.get("subtle_anomaly_flag", False))
        )
        if review_like:
            uncertainty = max(uncertainty, 0.65)

        uncertainty = float(np.clip(uncertainty, 0.0, 1.0))
        if uncertainty >= self.high_uncertainty_threshold:
            band = "high"
        elif uncertainty >= self.review_uncertainty_threshold:
            band = "moderate"
        else:
            band = "low"

        result["uncertainty_score"] = float(np.round(uncertainty, 3))
        result["uncertainty_band"] = band
        result["needs_manual_review"] = bool(uncertainty >= self.review_uncertainty_threshold)

        # "I don't know" is safer than an incorrect confident diagnosis.
        cls_l = str(result.get("classification", "")).strip().lower()
        if uncertainty >= self.no_guess_uncertainty_threshold and cls_l not in self.critical_arrhythmia_labels:
            result["is_arrhythmia"] = False
            result["classification"] = "I don't know - Clinical Review Required"
            result["model_used"] = f"{result.get('model_used', self.model_version)}+no-guess"
        return result

    def _attach_ood_signal_flag(self, result: Dict, signal_window: np.ndarray) -> Dict:
        """Flag out-of-distribution windows so frontend and clinicians can gate trust."""
        out = dict(result)
        if signal_window.size == 0:
            out["ood_flag"] = True
            out["ood_reason"] = "empty_window"
            return out

        z = self._normalize(signal_window)
        amp_span = float(np.percentile(z, 99) - np.percentile(z, 1))
        saturation_ratio = float(np.mean(np.abs(z) > 4.0))
        nan_ratio = float(np.mean(~np.isfinite(signal_window)))

        ood_flag = bool(
            amp_span > 12.0
            or saturation_ratio > 0.08
            or nan_ratio > 0.0
        )
        out["ood_flag"] = ood_flag
        if ood_flag:
            out["ood_reason"] = "distribution_shift_or_sensor_artifact"
            out["needs_manual_review"] = True
            out["uncertainty_band"] = "high"
            out["uncertainty_score"] = float(max(float(out.get("uncertainty_score", 0.0) or 0.0), 0.90))
            if str(out.get("classification", "")).strip().lower() not in self.critical_arrhythmia_labels:
                out["is_arrhythmia"] = False
                out["classification"] = "I don't know - Out-of-Distribution Signal"
        return out

    def _load_model_if_available(self) -> None:
        if keras is None:
            logger.warning("TensorFlow unavailable. Falling back to heuristic inference.")
            return
        if not self.model_path.exists():
            logger.info("Model file not found at %s. Using heuristic inference.", self.model_path)
            return

        try:
            self.model = keras.models.load_model(self.model_path, compile=False)
            self.model_version = f"keras:{self.model_path.name}"
            logger.info("Loaded ECG model: %s", self.model_version)
        except Exception as exc:
            logger.error("Failed to load ECG model (%s). Using heuristic fallback.", exc)
            self.model = None

    def _load_thresholds_if_available(self) -> None:
        if not self.thresholds_path.exists():
            return
        try:
            import json

            payload = json.loads(self.thresholds_path.read_text(encoding="utf-8"))
            thr = payload.get("binary_decision_threshold")
            if thr is not None:
                thr_f = float(thr)
                if 0.05 <= thr_f <= 0.99:
                    self.binary_decision_threshold = thr_f
                    logger.info("Loaded binary decision threshold=%.3f from %s", thr_f, self.thresholds_path)
        except Exception as exc:
            logger.warning("Failed to load thresholds file (%s): %s", self.thresholds_path, exc)

    @staticmethod
    def _normalize(window: np.ndarray) -> np.ndarray:
        std = float(np.std(window))
        if std < 1e-6:
            return np.zeros_like(window)
        return (window - float(np.mean(window))) / std

    def _infer_with_keras(self, signal_window: np.ndarray) -> Optional[Dict]:
        model = self.model
        if model is None:
            return None

        x = self._normalize(signal_window).astype(np.float32)[None, :, None]
        try:
            # Cast to Any to bypass strict type checking on the model object which might be seen as NoneType
            probs = np.array(cast(Any, model).predict(x, verbose=0)).reshape(-1)
            if probs.size == 1:
                af_prob = float(np.clip(probs[0], 0.0, 1.0))
                class_idx = 1 if af_prob >= self.binary_decision_threshold else 0
                confidence = af_prob if class_idx == 1 else 1.0 - af_prob
                probs_out = [1.0 - af_prob, af_prob, 0.0]
            else:
                probs = probs / max(np.sum(probs), 1e-6)
                class_idx = int(np.argmax(probs))
                confidence = float(np.clip(probs[class_idx], 0.0, 1.0))
                probs_out = [float(v) for v in probs[:3]]
                while len(probs_out) < 3:
                    probs_out.append(0.0)

            classification = self.labels[class_idx] if class_idx < len(self.labels) else self.labels[2]
            return {
                "is_arrhythmia": class_idx != 0,
                "classification": classification,
                "confidence": float(np.round(confidence, 3)),
                "probabilities": {
                    "normal": float(np.round(probs_out[0], 3)),
                    "afib": float(np.round(probs_out[1], 3)),
                    "other": float(np.round(probs_out[2], 3)),
                },
                "heart_rate_bpm": None,
                "rr_cv": None,
                "signal_quality": "good",
                "model_used": self.model_version,
                "explainability_map": None,
            }
        except Exception as exc:
            logger.warning("Model inference error: %s. Falling back to heuristic mode.", exc)
            return None

    def _infer_heuristic(self, signal_window: np.ndarray) -> Dict:
        if signal_window.size < 40:
            return {
                "is_arrhythmia": False,
                "classification": "Insufficient Signal",
                "confidence": 0.55,
                "probabilities": {"normal": 0.45, "afib": 0.25, "other": 0.30},
                "heart_rate_bpm": None,
                "rr_cv": None,
                "signal_quality": "poor",
                "model_used": self.model_version,
                "explainability_map": None,
            }

        z = self._normalize(signal_window)
        amp_span = float(np.percentile(z, 95) - np.percentile(z, 5))

        if amp_span < 0.1:
            return {
                "is_arrhythmia": False,
                "classification": "Disconnected",
                "confidence": 0.99,
                "probabilities": {"normal": 0.0, "afib": 0.0, "other": 0.0},
                "heart_rate_bpm": 0.0,
                "rr_cv": 0.0,
                "signal_quality": "disconnected",
                "model_used": self.model_version,
                "explainability_map": None,
            }

        peak_height = max(0.6, float(np.percentile(z, 88)))
        # Enforce physiologic lower bound on RR to avoid impossible HR artifacts.
        min_distance = int(0.20 * FS)
        peaks, _ = find_peaks(z, distance=min_distance, height=peak_height)

        if len(peaks) < 2:
            quality = "poor" if amp_span < 1.4 else "fair"
            return {
                "is_arrhythmia": False,  # Changed to False so noise doesn't trigger disease alerts
                "classification": "Poor Signal Quality" if quality == "poor" else "Normal Sinus Rhythm",
                "confidence": 0.72 if quality == "poor" else 0.62,
                "probabilities": {"normal": 0.62, "afib": 0.18, "other": 0.20},
                "heart_rate_bpm": None,
                "rr_cv": None,
                "signal_quality": quality,
                "model_used": self.model_version,
                "explainability_map": None,
            }

        rr = np.diff(peaks) / FS
        # Reject clearly non-physiologic RR intervals before deriving rhythm metrics.
        rr = rr[(rr >= 0.33) & (rr <= 1.80)]
        if rr.size < 2:
            quality = "fair" if amp_span >= 1.4 else "poor"
            return {
                "is_arrhythmia": False,
                "classification": "Normal Sinus Rhythm" if quality == "fair" else "Poor Signal Quality",
                "confidence": 0.60 if quality == "fair" else 0.72,
                "probabilities": {"normal": 0.60, "afib": 0.18, "other": 0.22},
                "heart_rate_bpm": None,
                "rr_cv": None,
                "signal_quality": quality,
                "model_used": self.model_version,
                "explainability_map": None,
            }

        rr_mean = float(np.mean(rr))
        rr_std = float(np.std(rr))
        rr_cv = float(rr_std / max(rr_mean, 1e-6))
        heart_rate = float(60.0 / max(float(np.median(rr)), 1e-6))

        is_af_like = rr_cv >= 0.13 and len(rr) >= 3
        is_tachy = heart_rate > 100.0
        is_vtach = heart_rate > 160.0
        is_flutter = 140.0 <= heart_rate <= 160.0 and rr_cv < 0.05
        is_vfib = rr_cv > 0.4 and amp_span > 2.0
        is_brady = heart_rate < 50.0

        if is_vfib:
            classification = "Ventricular Fibrillation (VF)"
            anomaly_score = 0.95
            feature_focus = "Chaotic, disorganized waveform"
        elif is_vtach:
            classification = "Ventricular Tachycardia (VT)"
            anomaly_score = 0.90
            feature_focus = "Fast rhythm, wide QRS complexes"
        elif is_flutter:
            classification = "Atrial Flutter"
            anomaly_score = 0.85
            feature_focus = "Sawtooth pattern (F-waves), rapid atrial rate"
        elif is_af_like:
            classification = "Atrial Fibrillation (AFib)"
            anomaly_score = min(1.0, 0.6 + rr_cv)
            feature_focus = "Irregularly irregular rhythm"
        elif is_brady:
            classification = "Heart Block (Bradycardia)"
            anomaly_score = min(1.0, 0.5 + (50.0 - heart_rate) / 40.0)
            feature_focus = "Prolonged intervals or dropped beats"
        elif is_tachy:
            classification = "Ventricular Tachycardia (VT)" if heart_rate > 130 else "Tachycardia Pattern"
            anomaly_score = min(1.0, 0.5 + (heart_rate - 110.0) / 80.0)
            feature_focus = "Sustained short RR intervals"
        else:
            classification = "Normal Sinus Rhythm"
            anomaly_score = max(0.0, 0.25 - rr_cv)
            feature_focus = "Stable RR intervals"

        confidence = float(np.clip(0.60 + anomaly_score * 0.35, 0.50, 0.97))
        normal_prob = max(0.0, 1.0 - anomaly_score)
        afib_prob = anomaly_score if "AFib" in classification else max(0.0, anomaly_score * 0.55)
        other_prob = max(0.0, 1.0 - normal_prob - afib_prob)
        denom = normal_prob + afib_prob + other_prob
        probs = {
            "normal": float(np.round(normal_prob / denom, 3)),
            "afib": float(np.round(afib_prob / denom, 3)),
            "other": float(np.round(other_prob / denom, 3)),
        }

        peaks_arr = np.asarray(peaks)
        i = int(np.argmax(np.abs(np.diff(rr)))) if len(rr) > 1 else 0
        start_ms = int(peaks_arr[i] / FS * 1000)
        end_ms = int(peaks_arr[min(i + 1, len(peaks_arr) - 1)] / FS * 1000)
        explainability_map = {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "intensity_score": float(np.round(float(min(0.99, 0.55 + anomaly_score * 0.4)), 3)),
            "feature_focus": feature_focus,
        }

        signal_quality = "good" if amp_span >= 1.5 else "fair"
        is_arrhythmia = classification not in ["Normal Sinus Rhythm"]
        return {
            "is_arrhythmia": is_arrhythmia,
            "classification": classification,
            "confidence": float(np.round(confidence, 3)),
            "probabilities": probs,
            "heart_rate_bpm": float(np.round(heart_rate, 1)),
            "rr_cv": float(np.round(rr_cv, 3)),
            "signal_quality": signal_quality,
            "model_used": self.model_version,
            "explainability_map": explainability_map if is_arrhythmia else None,
        }

    def _subtle_anomaly_score(self, signal_window: np.ndarray) -> tuple[float, Dict[str, float]]:
        """Return a high-sensitivity anomaly score tuned for subtle rhythm changes.

        This is a review-assist score, not a hard diagnosis.
        """
        if signal_window.size < 40:
            return 0.0, {"rr_cv": 0.0, "slope_energy": 0.0, "spike_ratio": 0.0}

        z = self._normalize(signal_window)
        peak_height = max(0.45, float(np.percentile(z, 82)))
        peaks, _ = find_peaks(z, distance=max(1, int(0.10 * FS)), height=peak_height)

        rr_cv = 0.0
        if len(peaks) >= 3:
            rr = np.diff(peaks) / FS
            rr_mean = float(np.mean(rr))
            rr_cv = float(np.std(rr) / max(rr_mean, 1e-6))

        slope_energy = float(np.mean(np.abs(np.diff(z))))
        spike_ratio = float(np.mean(np.abs(z) > 2.1))

        # Weighted blend: rhythm irregularity + morphology roughness + sparse spikes
        score = 0.50 * min(1.0, rr_cv / 0.20) + 0.30 * min(1.0, slope_energy / 0.22) + 0.20 * min(1.0, spike_ratio / 0.06)
        score = float(np.clip(score, 0.0, 1.0))
        return score, {
            "rr_cv": float(np.round(rr_cv, 4)),
            "slope_energy": float(np.round(slope_energy, 4)),
            "spike_ratio": float(np.round(spike_ratio, 4)),
        }

    def predict(self, cleaned_ecg_window: list) -> Dict:
        signal_window = np.array(cleaned_ecg_window, dtype=np.float32)
        if signal_window.size == 0:
            return {
                "is_arrhythmia": False,
                "classification": "No Signal",
                "confidence": 0.51,
                "probabilities": {"normal": 0.34, "afib": 0.33, "other": 0.33},
                "heart_rate_bpm": None,
                "rr_cv": None,
                "signal_quality": "poor",
                "model_used": self.model_version,
                "explainability_map": None,
                "subtle_anomaly_score": 0.0,
                "subtle_anomaly_flag": False,
            }

        heuristic_res = self._infer_heuristic(signal_window)
        keras_res = self._infer_with_keras(signal_window)

        if keras_res is None:
            res = heuristic_res
        else:
            # ML-first output with physiological context borrowed from heuristic branch.
            res = dict(keras_res)
            if res.get("heart_rate_bpm") is None:
                res["heart_rate_bpm"] = heuristic_res.get("heart_rate_bpm")
            if res.get("rr_cv") is None:
                res["rr_cv"] = heuristic_res.get("rr_cv")
            if res.get("explainability_map") is None:
                res["explainability_map"] = heuristic_res.get("explainability_map")
            res["signal_quality"] = heuristic_res.get("signal_quality", res.get("signal_quality", "fair"))
            res["model_used"] = self.model_version

            # Consensus calibration: if ML predicts broad/unspecific "Other Arrhythmia"
            # but heuristic rhythm metrics are strongly normal, prefer heuristic normal.
            ml_class = str(res.get("classification", ""))
            hr_h = heuristic_res.get("heart_rate_bpm")
            rr_h = heuristic_res.get("rr_cv")
            heuristic_conf = float(heuristic_res.get("confidence", 0.0) or 0.0)
            heuristic_quality = str(heuristic_res.get("signal_quality", "fair")).lower()
            heuristic_is_normal = str(heuristic_res.get("classification", "")) == "Normal Sinus Rhythm"
            ml_is_other = "Other Arrhythmia" in ml_class
            ml_is_critical = ml_class.strip().lower() in self.critical_arrhythmia_labels
            hr_ok = isinstance(hr_h, (int, float)) and 50.0 <= float(hr_h) <= 110.0
            rr_ok = isinstance(rr_h, (int, float)) and float(rr_h) <= 0.16
            heuristic_normal_support = (
                heuristic_is_normal
                and (
                    (hr_ok and rr_ok and heuristic_conf >= 0.65)
                    or (heuristic_quality in {"fair", "good"} and heuristic_conf >= 0.60)
                )
            )
            if ml_is_other and heuristic_is_normal and hr_ok and rr_ok:
                res = dict(heuristic_res)
                res["model_used"] = f"{self.model_version}+consensus-calibration"

            # If ML marks arrhythmia but heuristic evidence is strongly normal,
            # prefer the physiologic normal call for non-critical classes.
            if (
                bool(res.get("is_arrhythmia", False))
                and (not ml_is_critical)
                and heuristic_normal_support
            ):
                res = dict(heuristic_res)
                res["model_used"] = f"{self.model_version}+normal-consensus"

            # Safety net: if ML says normal but heuristic strongly indicates abnormal rhythm,
            # escalate to review mode rather than suppressing potential risk.
            if (
                self.enable_heuristic_safety_override
                and (not bool(res.get("is_arrhythmia", False)))
                and bool(heuristic_res.get("is_arrhythmia", False))
                and float(heuristic_res.get("confidence", 0.0)) >= 0.78
            ):
                res = dict(heuristic_res)
                res["model_used"] = f"{self.model_version}+heuristic-safety"

            # Hard safety floor for severe instability: never suppress clear danger signatures
            # such as extremely irregular rhythm or very high ventricular rate.
            if not bool(res.get("is_arrhythmia", False)):
                rr_h = heuristic_res.get("rr_cv")
                hr_h = heuristic_res.get("heart_rate_bpm")
                severe_rr = isinstance(rr_h, (int, float)) and float(rr_h) >= 0.35
                severe_hr = isinstance(hr_h, (int, float)) and float(hr_h) >= 130.0
                if severe_rr or severe_hr:
                    res["is_arrhythmia"] = True
                    res["classification"] = "Other Arrhythmia"
                    res["confidence"] = float(np.round(max(float(res.get("confidence", 0.0)), 0.70), 3))
                    res["probabilities"] = {"normal": 0.15, "afib": 0.25, "other": 0.60}
                    res["model_used"] = f"{self.model_version}+safety-floor"

            # Guardrail: for non-critical labels, require either heuristic support,
            # physiologic risk evidence, or very high ML confidence.
            if bool(res.get("is_arrhythmia", False)):
                cls_l = str(res.get("classification", "")).strip().lower()
                is_critical = cls_l in self.critical_arrhythmia_labels
                is_other_label = "other arrhythmia" in cls_l
                hr_h = heuristic_res.get("heart_rate_bpm")
                rr_h = heuristic_res.get("rr_cv")
                heuristic_conf = float(heuristic_res.get("confidence", 0.0) or 0.0)
                heuristic_support = bool(heuristic_res.get("is_arrhythmia", False))
                physiologic_support = (
                    (isinstance(rr_h, (int, float)) and float(rr_h) >= 0.14)
                    or (isinstance(hr_h, (int, float)) and (float(hr_h) < 48.0 or float(hr_h) > 115.0))
                )
                strong_ml = float(res.get("confidence", 0.0)) >= self.strong_ml_override_confidence

                # Scope stronger gating to "Other Arrhythmia" so AFib sensitivity is preserved.
                if (not is_critical) and is_other_label:
                    other_supported = (
                        physiologic_support
                        or (heuristic_support and heuristic_conf >= 0.65)
                        or (float(res.get("confidence", 0.0)) >= 0.75)
                    )
                    if not other_supported:
                        res["is_arrhythmia"] = False
                        res["classification"] = "Subtle Rhythm Irregularity (Review)"
                        res["model_used"] = f"{self.model_version}+other-consensus-gate"
                elif (not is_critical) and not (heuristic_support or physiologic_support or strong_ml):
                    res["is_arrhythmia"] = False
                    res["classification"] = "Subtle Rhythm Irregularity (Review)"
                    res["model_used"] = f"{self.model_version}+consensus-gate"

        subtle_score, subtle_metrics = self._subtle_anomaly_score(signal_window)
        subtle_rr_cv = float(subtle_metrics.get("rr_cv", 0.0) or 0.0)
        subtle_spike = float(subtle_metrics.get("spike_ratio", 0.0) or 0.0)
        subtle_flag = subtle_score >= 0.62 and (subtle_rr_cv >= 0.08 or subtle_spike >= 0.015)
        res["subtle_anomaly_score"] = float(np.round(subtle_score, 3))
        res["subtle_anomaly_flag"] = subtle_flag
        res["subtle_anomaly_metrics"] = subtle_metrics

        # Safety-focused escalation for likely missed arrhythmia windows.
        if (not bool(res.get("is_arrhythmia", False))) and subtle_score >= 0.75:
            res["is_arrhythmia"] = True
            res["classification"] = "Other Arrhythmia"
            res["confidence"] = float(np.round(max(float(res.get("confidence", 0.0)), 0.70), 3))
            res["probabilities"] = {"normal": 0.18, "afib": 0.24, "other": 0.58}
            res["model_used"] = f"{self.model_version}+subtle-safety-escalation"

        # If no hard arrhythmia but subtle score is high, raise a review class for early detection.
        if (not bool(res.get("is_arrhythmia", False))) and subtle_flag:
            # Keep as review-only flag to reduce false positives in screening mode.
            res["is_arrhythmia"] = False
            res["classification"] = "Subtle Rhythm Irregularity (Review)"
            res["confidence"] = float(np.round(max(float(res.get("confidence", 0.0)), 0.58), 3))
            res["probabilities"] = {"normal": 0.42, "afib": 0.22, "other": 0.36}
            if res.get("explainability_map") is None:
                res["explainability_map"] = {
                    "start_ms": 0,
                    "end_ms": int(len(signal_window) / FS * 1000),
                    "intensity_score": float(np.round(min(0.99, 0.45 + subtle_score * 0.5), 3)),
                    "feature_focus": "Subtle rhythm irregularity signature",
                }

        res = self._apply_decision_policy(res)
        res = self._attach_uncertainty(res)
        res = self._attach_ood_signal_flag(res, signal_window)
        return res

    def status(self) -> Dict:
        return {
            "model_loaded": self.model is not None,
            "model_used": self.model_version,
            "model_path": str(self.model_path),
        }


edge_ai = ArrhythmiaEngine()


def predict_arrhythmia(cleaned_ecg_window: list) -> Dict:
    return edge_ai.predict(cleaned_ecg_window)


def get_model_status() -> Dict:
    return edge_ai.status()
