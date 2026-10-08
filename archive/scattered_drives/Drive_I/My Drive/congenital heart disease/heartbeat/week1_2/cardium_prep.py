"""
cardium_prep.py — Week 1–2 data engineering for the CARDIUM fetal-CHD dataset.

Week 1: image manifest + fold validation, exact/near-duplicate detection,
        clinical cleaning into one typed row per patient, fold-safe encoders.
Week 2: ultrasound-fan masking, caliper/overlay detection + inpainting,
        shortcut audit statistics, QA contact sheets.

Every function is pure w.r.t. its inputs and writes nothing unless told to.
"""
from __future__ import annotations

import hashlib, json, os, re, math, warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

LABELS = {"CHD": 1, "Non_CHD": 0}
PID_RE = re.compile(r"(aedxf\d{5}rrfgkl0)")

# ----------------------------------------------------------------------------
# 1. Manifest
# ----------------------------------------------------------------------------

def build_manifest(flat_root: Path) -> pd.DataFrame:
    """One row per image in CARDIUM_dataset/{CHD,Non_CHD}/<pid>/<k>_<pid>.png."""
    rows = []
    for cls, y in LABELS.items():
        d = Path(flat_root) / cls
        if not d.exists():
            raise FileNotFoundError(d)
        for pdir in sorted(p for p in d.iterdir() if p.is_dir()):
            for f in sorted(pdir.glob("*.png")):
                m = re.match(r"(\d+)_", f.name)
                rows.append(dict(pid=pdir.name, label=y, frame=int(m.group(1)) if m else -1,
                                 path=str(f), bytes=f.stat().st_size))
    df = pd.DataFrame(rows)
    df["img_id"] = df["pid"] + "/" + df["frame"].astype(str)
    return df


def read_folds(fold_root: Path, n_folds: int = 3) -> tuple[pd.DataFrame, list[str]]:
    """Return (pid, label_dir, test_fold) and a list of integrity problems."""
    problems, rec = [], {}
    for k in range(1, n_folds + 1):
        for split in ("train", "test"):
            for cls in LABELS:
                d = Path(fold_root) / f"fold_{k}" / split / cls
                if not d.exists():
                    problems.append(f"missing dir {d}")
                    continue
                for p in d.iterdir():
                    if not p.is_dir():
                        continue
                    r = rec.setdefault(p.name, {"cls": set(), "test": [], "train": []})
                    r["cls"].add(cls)
                    r[split].append(k)
    rows = []
    for pid, r in rec.items():
        if len(r["cls"]) != 1:
            problems.append(f"{pid}: label differs across fold dirs {r['cls']}")
        if len(r["test"]) != 1:
            problems.append(f"{pid}: in {len(r['test'])} test folds {r['test']}")
        overlap = set(r["test"]) & set(r["train"])
        if overlap:
            problems.append(f"{pid}: train AND test in fold {overlap}  <-- LEAK")
        if len(set(r["test"]) | set(r["train"])) != n_folds:
            problems.append(f"{pid}: not present in every fold (train∪test)")
        rows.append(dict(pid=pid, label_dir=LABELS[sorted(r["cls"])[0]],
                         test_fold=r["test"][0] if r["test"] else -1))
    return pd.DataFrame(rows), problems


# ----------------------------------------------------------------------------
# 2. Hashing / duplicates
# ----------------------------------------------------------------------------

def sha1_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def dhash(img_gray: np.ndarray, size: int = 16) -> int:
    """Difference hash (size*size bits) of a grayscale uint8 array."""
    import cv2
    small = cv2.resize(img_gray, (size + 1, size), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    v = 0
    for b in bits:
        v = (v << 1) | int(b)
    return v


def _popcount64(x: np.ndarray) -> np.ndarray:
    x = x - ((x >> np.uint64(1)) & np.uint64(0x5555555555555555))
    x = (x & np.uint64(0x3333333333333333)) + ((x >> np.uint64(2)) & np.uint64(0x3333333333333333))
    x = (x + (x >> np.uint64(4))) & np.uint64(0x0F0F0F0F0F0F0F0F)
    return ((x * np.uint64(0x0101010101010101)) >> np.uint64(56)).astype(np.int64)


def near_duplicate_pairs(hashes: list[int], max_hamming: int = 10, n_bits: int = 256,
                         block: int = 512) -> pd.DataFrame:
    """All pairs (i<j) with Hamming(dhash) <= max_hamming. Hashes up to 256 bits,
    split into 64-bit words. O(N^2) vectorised in blocks; ~7k images is seconds."""
    words = n_bits // 64
    H = np.zeros((len(hashes), words), dtype=np.uint64)
    for i, h in enumerate(hashes):
        for w in range(words):
            H[i, w] = np.uint64((h >> (64 * w)) & 0xFFFFFFFFFFFFFFFF)
    out = []
    n = len(H)
    for s in range(0, n, block):
        A = H[s:s + block]
        d = np.zeros((len(A), n), dtype=np.int64)
        for w in range(words):
            d += _popcount64(A[:, None, w] ^ H[None, :, w])
        ii, jj = np.nonzero(d <= max_hamming)
        gi = ii + s
        keep = jj > gi
        out.append(np.stack([gi[keep], jj[keep], d[ii[keep], jj[keep]]], 1))
    arr = np.concatenate(out) if out else np.zeros((0, 3), int)
    return pd.DataFrame(arr, columns=["i", "j", "hamming"])


# ----------------------------------------------------------------------------
# 3. Clinical cleaning
# ----------------------------------------------------------------------------

PER_VISIT = ["age", "gestational_week_of_imaging", "body_mass_index", "gestational_age"]
LABS = ["platelets", "hemoglobin", "hematocrit", "white_blood_cells", "neutrophils"]
ORDINAL = ["thromboembolic_risk", "psychosocial_risk", "depression_screening", "physical_activity"]
BINARY = ["tobacco_use", "nutritional_deficiencies", "alcohol_use"]
COUNTS = ["pregnancies", "vaginal_births", "cesarean_sections", "miscarriages", "ectopic_pregnancies"]
# Recorded possibly BECAUSE a CHD was suspected -> exclude from screening-time models.
POST_DX_SUSPECT = ["chromosomal_abnormality", "screening_procedures"]
HISTORY = {"pathological_history": "hx", "hereditary_history": "fam", "pharmacological_history": "rx"}

RANGES = {  # plausible physiological ranges; outside -> NaN (logged)
    "age": (12, 60), "gestational_week_of_imaging": (4, 43), "body_mass_index": (12, 70),
    "gestational_age": (4, 43), "platelets": (10_000, 1_000_000), "hemoglobin": (4, 22),
    "hematocrit": (10, 65), "white_blood_cells": (1_000, 60_000), "neutrophils": (100, 50_000),
}
TOKEN_SYNONYMS = {"asa": "aspirin", "acetylsalicylic_acid": "aspirin"}
NULL_TOKENS = {"none", "na", "nan", "", "-1"}


def _as_list(v):
    if isinstance(v, list):
        return v
    return [] if v is None else [v]


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return np.nan
    return np.nan if f == -1 else f


def _in_range(field, v, log, pid):
    if np.isnan(v) or field not in RANGES:
        return v
    lo, hi = RANGES[field]
    if not (lo <= v <= hi):
        log.append(dict(pid=pid, field=field, raw=v, action=f"out of range [{lo},{hi}] -> NaN"))
        return np.nan
    return v


def _parse_date(s, log, pid):
    s = str(s)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return pd.Timestamp(s)
    if s in ("-1", "", "None"):
        return pd.NaT
    log.append(dict(pid=pid, field="ultrasound_date", raw=s,
                    action="non-ISO / ambiguous date -> NaT"))
    return pd.NaT


def clean_clinical(records: list[dict], min_token_count: int = 10):
    """Return (patients_df, quality_log_df). One row per patient, all numeric,
    NaN for missing (never -1), explicit *_missing flags, multi-hot histories."""
    log, rows, token_rows = [], [], []
    for x in records:
        pid = x["id"]
        r = {"pid": pid, "CHD": int(x["CHD"])}
        lens = []
        for f in PER_VISIT:
            raw = x.get(f)
            if not isinstance(raw, list):
                log.append(dict(pid=pid, field=f, raw=raw, action="scalar -> 1-element list"))
            vals = [_in_range(f, _num(v), log, pid) for v in _as_list(raw)]
            lens.append(len(vals))
            good = [v for v in vals if not np.isnan(v)]
            r[f"{f}_first"] = good[0] if good else np.nan
            r[f"{f}_n"] = len(good)
            if f in ("gestational_week_of_imaging", "gestational_age"):
                r[f"{f}_min"] = min(good) if good else np.nan
                r[f"{f}_max"] = max(good) if good else np.nan
        dates_raw = _as_list(x.get("ultrasound_date"))
        if not isinstance(x.get("ultrasound_date"), list):
            log.append(dict(pid=pid, field="ultrasound_date", raw=x.get("ultrasound_date"),
                            action="scalar -> 1-element list"))
        dates = [d for d in (_parse_date(s, log, pid) for s in dates_raw) if not pd.isna(d)]
        r["us_date_first"] = min(dates) if dates else pd.NaT
        r["us_date_last"] = max(dates) if dates else pd.NaT
        r["us_year_first"] = r["us_date_first"].year if dates else np.nan
        r["n_us_dates"] = len(dates)
        lens.append(len(dates_raw))
        # visit-count proxy: shortcut candidate, kept for auditing only
        r["n_visit_entries"] = max(lens) if lens else 0

        for f in LABS:
            raw = x.get(f)
            if isinstance(raw, list):
                log.append(dict(pid=pid, field=f, raw=raw, action="list -> first value"))
                raw = raw[0] if raw else -1
            r[f] = _in_range(f, _num(raw), log, pid)
        for f in ORDINAL + BINARY + COUNTS + POST_DX_SUSPECT:
            r[f] = _num(x.get(f))

        for f, pre in HISTORY.items():
            toks = []
            for t in _as_list(x.get(f)):
                t = str(t).strip().lower()
                t = TOKEN_SYNONYMS.get(t, t)
                if t not in NULL_TOKENS:
                    toks.append(t)
            toks = sorted(set(toks))
            r[f"{pre}_n"] = len(toks)
            token_rows.append((pid, pre, toks))
        rows.append(r)

    df = pd.DataFrame(rows).set_index("pid")
    # multi-hot for tokens with enough support (rare ones -> <pre>_rare_n)
    from collections import Counter
    cnt = Counter((pre, t) for _, pre, toks in token_rows for t in toks)
    keep = {k for k, c in cnt.items() if c >= min_token_count}
    mh = {}
    for pid, pre, toks in token_rows:
        d = mh.setdefault(pid, {})
        d[f"{pre}_rare_n"] = d.get(f"{pre}_rare_n", 0)
        for t in toks:
            if (pre, t) in keep:
                d[f"{pre}__{t}"] = 1
            else:
                d[f"{pre}_rare_n"] += 1
    mh = pd.DataFrame.from_dict(mh, orient="index").fillna(0).astype(np.int8)
    df = df.join(mh)
    # raw token lists (for fold-safe WoE later)
    tok = pd.DataFrame([(p, pre, "|".join(t)) for p, pre, t in token_rows],
                       columns=["pid", "pre", "tokens"]).pivot(index="pid", columns="pre", values="tokens")
    tok.columns = [f"{c}_tokens" for c in tok.columns]
    df = df.join(tok)
    # missing flags for every numeric column with any NaN
    for c in [c for c in df.columns if df[c].dtype.kind == "f" and df[c].isna().any()]:
        df[f"{c}_missing"] = df[c].isna().astype(np.int8)
    return df, pd.DataFrame(log)


# ----------------------------------------------------------------------------
# 4. Fold-safe encoders (fit on train patients ONLY)
# ----------------------------------------------------------------------------

def woe_table(token_series: pd.Series, y: pd.Series, alpha: float = 0.5) -> dict:
    """Additively smoothed WoE per token: ln( P(tok|y=1) / P(tok|y=0) )."""
    pos, neg = (y == 1).sum(), (y == 0).sum()
    counts = {}
    for toks, yy in zip(token_series.fillna(""), y):
        for t in filter(None, toks.split("|")):
            c = counts.setdefault(t, [0, 0])
            c[int(yy == 1)] += 1  # c[1]=pos, c[0]=neg
    return {t: math.log(((c[1] + alpha) / (pos + 2 * alpha)) / ((c[0] + alpha) / (neg + 2 * alpha)))
            for t, c in counts.items()}


def apply_woe(token_series: pd.Series, table: dict) -> pd.DataFrame:
    """Per patient: sum, max, min WoE of known tokens; unseen tokens -> 0; empty -> 0 + flag."""
    out = []
    for toks in token_series.fillna(""):
        w = [table.get(t, 0.0) for t in filter(None, toks.split("|"))]
        out.append((sum(w), max(w) if w else 0.0, min(w) if w else 0.0, int(not w)))
    return pd.DataFrame(out, index=token_series.index, columns=["woe_sum", "woe_max", "woe_min", "woe_empty"])


def fold_features(df: pd.DataFrame, train_idx, test_idx, numeric_cols: list[str],
                  use_woe: bool = True, woe_on_all_rows: bool = False):
    """Standardise numerics with train stats, median-impute (flags already exist),
    optionally add WoE features fitted on TRAIN only. woe_on_all_rows=True reproduces
    the leaky variant for the audit — never use it for reported results."""
    tr, te = df.loc[train_idx], df.loc[test_idx]
    med = tr[numeric_cols].median()
    mu = tr[numeric_cols].fillna(med).mean()
    sd = tr[numeric_cols].fillna(med).std().replace(0, 1)
    Xtr = ((tr[numeric_cols].fillna(med) - mu) / sd)
    Xte = ((te[numeric_cols].fillna(med) - mu) / sd)
    if use_woe:
        fit_rows = df if woe_on_all_rows else tr
        for c in [c for c in df.columns if c.endswith("_tokens")]:
            tab = woe_table(fit_rows[c], fit_rows["CHD"])
            Xtr = Xtr.join(apply_woe(tr[c], tab).add_prefix(c.replace("_tokens", "") + "_"))
            Xte = Xte.join(apply_woe(te[c], tab).add_prefix(c.replace("_tokens", "") + "_"))
    return Xtr, Xte


# ----------------------------------------------------------------------------
# 5. Week 2 — fan mask, caliper / overlay detection, inpainting
# ----------------------------------------------------------------------------

@dataclass
class MaskCfg:
    thr: int = 12             # gray level separating fan from pure-black background
    min_blob: int = 3000      # blobs smaller than this (text glyphs, markers) are dropped
    close_k: int = 21         # closing kernel to join speckle into one fan
    erode_px: int = 4         # shave the fan rim
    top_band: int = 0         # rows to force-blank (0 = auto from fan)


# Fixed Voluson on-screen UI zones, as fractions of (W, H): (x0, y0, x1, y1).
# Verify/adjust with ui_heatmap() on YOUR data before trusting them.
UI_ZONES = [
    (0.83, 0.00, 1.00, 0.27),   # top-right acquisition parameter block (preset, Hz, depth, gain)
    (0.86, 0.92, 1.00, 1.00),   # bottom-right measurement read-out box ("1 D 0.19cm")
    (0.00, 0.00, 1.00, 0.075),  # top banner
    (0.00, 0.08, 0.02, 0.16),   # left orientation marker
]


def ui_zone_mask(h: int, w: int, zones=UI_ZONES) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    for x0, y0, x1, y1 in zones:
        m[int(y0 * h):int(math.ceil(y1 * h)), int(x0 * w):int(math.ceil(x1 * w))] = 1
    return m


def fan_mask(rgb: np.ndarray, cfg: MaskCfg = MaskCfg()) -> np.ndarray:
    """Binary mask (uint8 0/1) of the ultrasound sector. Overlay text/markers are
    separate small components and are removed before the hull is taken."""
    import cv2
    gray = rgb.max(axis=2)
    b = (gray > cfg.thr).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(b, 8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= cfg.min_blob
    b = keep[lab].astype(np.uint8)
    b = cv2.morphologyEx(b, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.close_k,) * 2))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(b, 8)
    if n <= 1:
        return np.zeros(gray.shape, np.uint8)
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    b = (lab == big).astype(np.uint8)
    cnts, _ = cv2.findContours(b, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hull = cv2.convexHull(np.concatenate(cnts))
    m = np.zeros_like(b)
    cv2.fillConvexPoly(m, hull, 1)
    if cfg.erode_px:
        m = cv2.erode(m, np.ones((2 * cfg.erode_px + 1,) * 2, np.uint8))
    return m & (1 - ui_zone_mask(*m.shape))


def color_masks(rgb: np.ndarray):
    """Pixel masks for (a) yellow overlay (calipers / measurement text),
    (b) Doppler colour (saturated red/blue/orange flow), (c) any saturated colour."""
    import cv2
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    sat = (s > 90) & (v > 90)
    yellow = sat & (h >= 22) & (h <= 38)           # OpenCV hue 0-179; yellow ≈ 30
    red = sat & ((h <= 12) | (h >= 165))
    blue = sat & (h >= 95) & (h <= 130)
    return yellow.astype(np.uint8), (red | blue).astype(np.uint8), sat.astype(np.uint8)


def thin_part(mask: np.ndarray, k: int = 5, max_comp: int = 600) -> np.ndarray:
    """Thin, small strokes = calipers / dotted lines / glyphs. Pixels that vanish under
    morphological opening AND belong to a small connected component of the original
    mask (filled Doppler blobs are large, so their ragged edges are excluded)."""
    import cv2
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    thin = mask & (1 - opened)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    small = np.zeros(n, bool)
    small[1:] = stats[1:, cv2.CC_STAT_AREA] <= max_comp
    return (thin & small[lab]).astype(np.uint8)


def analyse_and_clean(path: str, out_path: str | None = None, max_side: int = 640,
                      cfg: MaskCfg = MaskCfg(), overlay_size: int = 96):
    """Process one image. Returns a dict of audit features and (optionally) writes the
    masked + caliper-inpainted, fan-cropped image. Also returns a small grayscale
    'overlay-only' thumbnail (everything OUTSIDE the fan) for the Week-3 shortcut baseline."""
    import cv2
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        return dict(path=path, ok=False)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    H, W = rgb.shape[:2]
    fan = fan_mask(rgb, cfg)
    yellow, doppler, sat = color_masks(rgb)
    y_thin = thin_part(yellow)
    y_in_fan = y_thin & fan
    dop_in_fan = doppler & fan
    # yellow anywhere outside the anatomy mask (read-out box, labels)
    y_out = yellow & (1 - fan)
    zones = ui_zone_mask(H, W)
    readout = yellow[int(0.92 * H):, int(0.86 * W):]
    feats = dict(
        path=path, ok=True, H=H, W=W,
        fan_frac=float(fan.mean()),
        caliper_px=int(y_in_fan.sum()),
        yellow_blob_px=int((yellow & fan).sum() - y_in_fan.sum()),
        yellow_outside_px=int(y_out.sum()),
        doppler_px=int(dop_in_fan.sum()),
        doppler_frac=float(dop_in_fan.sum() / max(fan.sum(), 1)),
        sat_outside_px=int((sat & (1 - fan)).sum()),
        readout_px=int(readout.sum()),
    )
    feats["has_caliper"] = feats["caliper_px"] >= 20 or feats["readout_px"] >= 40
    feats["is_doppler"] = feats["doppler_frac"] >= 0.005
    feats["dhash"] = dhash(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
    # overlay-only thumbnail (inverse mask) for the shortcut probe
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    ov = (gray * (1 - fan)).astype(np.uint8)
    feats["overlay_thumb"] = cv2.resize(ov, (overlay_size, overlay_size), interpolation=cv2.INTER_AREA)
    if out_path:
        clean = rgb.copy()
        inpaint_m = cv2.dilate(y_in_fan, np.ones((5, 5), np.uint8))
        if inpaint_m.any():
            clean = cv2.inpaint(clean, inpaint_m * 255, 3, cv2.INPAINT_TELEA)
        clean = clean * fan[..., None]
        ys, xs = np.nonzero(fan)
        if len(ys):
            clean = clean[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        h, w = clean.shape[:2]
        s = max_side / max(h, w)
        if s < 1:
            clean = cv2.resize(clean, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(out_path, cv2.cvtColor(clean, cv2.COLOR_RGB2BGR))
    return feats


def ui_heatmap(paths: list[str], size=(256, 204)) -> np.ndarray:
    """Per-pixel frequency (0-1) of overlay-like pixels (saturated colour, or near-white
    thin strokes) across images, at a common resolution. Bright spots OUTSIDE the
    UI_ZONES rectangles mean burned-in text the static zones miss."""
    import cv2
    acc = np.zeros(size[::-1], np.float32)
    for p in paths:
        bgr = cv2.imread(p)
        if bgr is None:
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        _, _, sat = color_masks(rgb)
        white = ((rgb.min(axis=2) > 225)).astype(np.uint8)
        ov = np.clip(thin_part(white, 3, 400) + thin_part(sat, 3, 400), 0, 1).astype(np.float32)
        acc += cv2.resize(ov, size, interpolation=cv2.INTER_AREA) > 0
    return acc / max(len(paths), 1)


def contact_sheet(paths: list[str], titles: list[str], out_png: str, ncol: int = 6, cell: int = 256):
    import cv2
    n = len(paths)
    if n == 0:
        return
    nrow = math.ceil(n / ncol)
    sheet = np.full((nrow * (cell + 22), ncol * cell, 3), 255, np.uint8)
    for i, (p, t) in enumerate(zip(paths, titles)):
        im = cv2.imread(p)
        if im is None:
            continue
        h, w = im.shape[:2]
        s = cell / max(h, w)
        im = cv2.resize(im, (int(w * s), int(h * s)))
        r, c = divmod(i, ncol)
        y0, x0 = r * (cell + 22) + 22, c * cell
        sheet[y0:y0 + im.shape[0], x0:x0 + im.shape[1]] = im
        cv2.putText(sheet, t[:34], (x0 + 3, y0 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)
    cv2.imwrite(out_png, sheet)


# ----------------------------------------------------------------------------
# 6. Small stats helpers
# ----------------------------------------------------------------------------

def rate_by_class(df: pd.DataFrame, flag: str, label: str = "label") -> dict:
    from scipy.stats import fisher_exact
    t = pd.crosstab(df[label], df[flag].astype(bool)).reindex(index=[0, 1], columns=[False, True], fill_value=0)
    orr, p = fisher_exact(t.values)
    return dict(flag=flag, rate_nonCHD=t.loc[0, True] / t.loc[0].sum(),
                rate_CHD=t.loc[1, True] / t.loc[1].sum(), odds_ratio=orr, p_fisher=p,
                n_nonCHD=int(t.loc[0].sum()), n_CHD=int(t.loc[1].sum()))


def boot_auc(y, s, n=2000, seed=0):
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(seed)
    y, s = np.asarray(y), np.asarray(s)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        vals.append(roc_auc_score(y[i], s[i]))
    return roc_auc_score(y, s), np.percentile(vals, 2.5), np.percentile(vals, 97.5)
