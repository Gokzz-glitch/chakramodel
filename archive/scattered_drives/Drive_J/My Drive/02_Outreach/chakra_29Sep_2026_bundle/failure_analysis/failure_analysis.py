"""
failure_analysis.py — why does a model fail, image by image?

Joins per-image predictions (one or more models/seeds) with the per-image test-set anatomy from
test_anatomy.py, then reports:
  A. Dice and miss rate (Dice < 0.1) by polyp-size bin x dataset
  B. miss rate by sharpness / colour-contrast tertile, specular, border contact, multiplicity
  C. multivariable regression of per-image Dice on standardised anatomy features (+ bootstrap CIs)
  D. size-mix decomposition: how much of each unseen set's gap to Kvasir+ClinicDB is explained by
     its polyp-size distribution alone (reweighting), and how much remains
  E. cross-model failure overlap: Jaccard of miss sets, the images every model misses, hardest images

Inputs accepted (--pred, repeatable; model name = file stem unless the file has a 'model' column):
  * chakraseg_v3 per_image.csv            (split, image, gated_dice / raw_dice)
  * any CSV / JSON list with an image path/name column and a dice column (auto-detected)
Usage:
  python failure_analysis.py --anatomy anatomy/anatomy.csv --pred runA/per_image.csv --pred runB/per_image.csv --out fa_report
"""
import argparse, json, os, re

import numpy as np
import pandas as pd

DS_PATTERNS = [("ETIS", r"etis"), ("ColonDB", r"colon[-_ ]?db|cvc[-_]?colondb"), ("CVC-300", r"cvc[-_ ]?300|endoscene|cvc[-_]?t\b"),
               ("ClinicDB", r"clinic"), ("Kvasir", r"kvasir")]
ANAT_MAP = {"Kvasir": "Kvasir", "CVC-ClinicDB": "ClinicDB", "CVC-ColonDB": "ColonDB",
            "ETIS-LaribPolypDB": "ETIS", "CVC-300": "CVC-300"}
TRAINLIKE = ["Kvasir", "ClinicDB"]
UNSEEN = ["ColonDB", "ETIS", "CVC-300"]
SIZE_BINS = [0, 0.01, 0.03, 0.05, 0.15, 1.01]
SIZE_LAB = ["<1%", "1-3%", "3-5%", "5-15%", ">=15%"]


def which_ds(*texts):
    t = " ".join(str(x) for x in texts if isinstance(x, str)).lower()
    for name, pat in DS_PATTERNS:
        if re.search(pat, t):
            return name
    return None


def load_pred(path, tag):
    if path.endswith(".json"):
        d = json.load(open(path))
        if isinstance(d, dict):
            d = d.get("per_image", d.get("images", d))
            if isinstance(d, dict):
                d = pd.DataFrame(d).to_dict("records")
        df = pd.DataFrame(d)
    else:
        df = pd.read_csv(path)
    low = {c.lower(): c for c in df.columns}
    icol = next((low[c] for c in ("image", "image_path", "path", "file", "name", "img") if c in low), None)
    dcol = next((low[c] for c in (tag + "_dice", "gated_dice", "dice", "raw_dice", "mdice") if c in low), None)
    if icol is None or dcol is None:
        raise SystemExit(f"[pred] {path}: need an image column and a dice column; have {list(df.columns)}")
    scol = next((low[c] for c in ("split", "dataset", "test_set", "subset") if c in low), None)
    out = pd.DataFrame({"image": df[icol].astype(str).map(lambda p: os.path.splitext(os.path.basename(p.replace("\\", "/")))[0]),
                        "dice": pd.to_numeric(df[dcol], errors="coerce")})
    out["ds"] = [which_ds(df[scol].iloc[i] if scol else "", df[icol].iloc[i]) for i in range(len(df))]
    out["model"] = df[low["model"]].astype(str) if "model" in low else os.path.basename(os.path.dirname(path)) or os.path.splitext(os.path.basename(path))[0]
    out["seed"] = df[low["seed"]] if "seed" in low else 0
    return out.dropna(subset=["dice", "ds"])


def zs(x):
    x = np.asarray(x, float)
    return (x - np.nanmean(x)) / (np.nanstd(x) + 1e-12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anatomy", required=True)
    ap.add_argument("--pred", action="append", required=True)
    ap.add_argument("--tag", default="gated", help="which dice column to prefer in chakraseg per_image files")
    ap.add_argument("--out", default="fa_report")
    ap.add_argument("--boot", type=int, default=500)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    an = pd.read_csv(a.anatomy)
    an["ds"] = an["dataset"].map(ANAT_MAP).fillna(an["dataset"])
    an["image"] = an["image"].astype(str)
    P = pd.concat([load_pred(p, a.tag) for p in a.pred], ignore_index=True)
    # average seeds within a model (the E3 convention), then join anatomy
    P = P.groupby(["model", "ds", "image"], as_index=False)["dice"].mean()
    D = P.merge(an, on=["ds", "image"], how="inner")
    unmatched = len(P) - len(D)
    D["miss"] = (D["dice"] < 0.1).astype(float)
    D["size_bin"] = pd.cut(D["area"], SIZE_BINS, labels=SIZE_LAB, right=False)
    L = [f"# Failure analysis", "", f"models: {sorted(D.model.unique())}; matched images: {len(D)}"
         f" (unmatched predictions: {unmatched})", ""]

    # A. size bins
    L += ["## A. Dice (miss rate) by polyp size x dataset", ""]
    for m, dm in D.groupby("model"):
        L += [f"**{m}**", "", "| size (share of frame) | " + " | ".join(d for d in TRAINLIKE + UNSEEN) + " |",
              "|---|" + "---|" * 5]
        for b in SIZE_LAB:
            cells = []
            for d in TRAINLIKE + UNSEEN:
                s = dm[(dm.ds == d) & (dm.size_bin == b)]
                cells.append("" if s.empty else f"{s.dice.mean():.3f} ({100 * s.miss.mean():.0f}%, n={len(s)})")
            L.append(f"| {b} | " + " | ".join(cells) + " |")
        L.append("")

    # B. tertiles of other factors (tertiles computed on the pooled anatomy, so they are comparable)
    L += ["## B. Miss rate (Dice < 0.1) by acquisition factor (pooled over datasets)", ""]
    facs = {"sharpness (Laplacian var @352)": "sharp", "polyp sharpness": "sharp_polyp",
            "colour contrast ΔE (polyp vs ring)": "dE_lab", "specular share": "spec", "brightness": "bright"}
    L += ["| factor | model | low tertile | mid | high | Dice low / high |", "|---|---|---|---|---|---|"]
    for lab, col in facs.items():
        qs = np.nanquantile(an[col], [1 / 3, 2 / 3])
        for m, dm in D.groupby("model"):
            t = np.digitize(dm[col], qs)
            r = [dm.miss[t == k].mean() for k in range(3)]
            dl, dh = dm.dice[t == 0].mean(), dm.dice[t == 2].mean()
            L.append(f"| {lab} | {m} | {100 * r[0]:.1f}% | {100 * r[1]:.1f}% | {100 * r[2]:.1f}% | {dl:.3f} / {dh:.3f} |")
    for lab, col in (("touches image border", "border"), ("more than one polyp", "n_polyps")):
        for m, dm in D.groupby("model"):
            f = dm[col] > (0 if col == "border" else 1)
            L.append(f"| {lab} | {m} | yes {100 * dm.miss[f].mean():.1f}% (n={int(f.sum())}) | | no {100 * dm.miss[~f].mean():.1f}% | {dm.dice[f].mean():.3f} / {dm.dice[~f].mean():.3f} |")
    L.append("")

    # C. regression
    L += ["## C. What explains per-image Dice? (OLS on standardised features; 95% bootstrap CI)", "",
          "Positive coefficient = larger values of the feature go with higher Dice. Dataset dummies absorb "
          "centre effects, so coefficients are *within-dataset* associations.", ""]
    feats = {"log area": np.log(D["area"].clip(1e-5)), "log sharpness": np.log(D["sharp"].clip(1e-3)),
             "colour contrast ΔE": D["dE_lab"], "specular": D["spec"], "black border": D["black"],
             "border contact": D["border"], "multi-polyp": (D["n_polyps"] > 1).astype(float),
             "off-centre": D["central"]}
    rng = np.random.default_rng(0)
    for m, idx in D.groupby("model").groups.items():
        dm = D.loc[idx]
        X = np.column_stack([zs(v.loc[idx]) for v in feats.values()])
        dums = pd.get_dummies(dm["ds"], drop_first=True).astype(float).values
        X = np.column_stack([np.ones(len(dm)), X, dums])
        ok = ~np.isnan(X).any(1) & dm["dice"].notna().values
        X, y = X[ok], dm["dice"].values[ok]
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        bs = []
        for _ in range(a.boot):
            ii = rng.integers(0, len(y), len(y))
            bs.append(np.linalg.lstsq(X[ii], y[ii], rcond=None)[0])
        bs = np.array(bs)
        r2 = 1 - ((y - X @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        L += [f"**{m}** (n={len(y)}, R² = {r2:.3f})", "", "| feature | coef (Dice per 1 SD) | 95% CI |", "|---|---|---|"]
        for j, name in enumerate(feats, start=1):
            lo, hi = np.percentile(bs[:, j], [2.5, 97.5])
            star = " *" if (lo > 0 or hi < 0) else ""
            L.append(f"| {name} | {beta[j]:+.3f}{star} | [{lo:+.3f}, {hi:+.3f}] |")
        L.append("")

    # D. size-mix decomposition
    L += ["## D. How much of the unseen-set gap is polyp size?", "",
          "Counterfactual = Dice the model would score on the train-like sets (Kvasir + ClinicDB) if their "
          "polyps had the unseen set's size distribution (reweighting by size bin).", "",
          "| model | unseen set | train-like Dice | unseen Dice | size-reweighted train-like | gap explained by size |",
          "|---|---|---|---|---|---|"]
    for m, dm in D.groupby("model"):
        tl = dm[dm.ds.isin(TRAINLIKE)]
        tl_bin = tl.groupby("size_bin", observed=False).dice.mean()
        for u in UNSEEN:
            du = dm[dm.ds == u]
            if du.empty or tl.empty:
                continue
            w = du.size_bin.value_counts(normalize=True)
            common = [b for b in w.index if not np.isnan(tl_bin.get(b, np.nan))]
            cf = float(sum(w[b] * tl_bin[b] for b in common) / max(1e-9, w[common].sum()))
            gap = tl.dice.mean() - du.dice.mean()
            expl = (tl.dice.mean() - cf) / gap if abs(gap) > 1e-6 else float("nan")
            L.append(f"| {m} | {u} | {tl.dice.mean():.3f} | {du.dice.mean():.3f} | {cf:.3f} | {100 * expl:.0f}% |")
    L.append("")

    # E. cross-model overlap
    models = sorted(D.model.unique())
    if len(models) > 1:
        W = D.pivot_table(index=["ds", "image"], columns="model", values="dice")
        W = W.dropna()
        miss = W < 0.1
        L += ["## E. Do models fail on the same images?", "", "| | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
        for m1 in models:
            cells = []
            for m2 in models:
                a_, b_ = miss[m1], miss[m2]
                u = (a_ | b_).sum()
                cells.append(f"{(a_ & b_).sum() / u:.2f}" if u else "")
            L.append(f"| {m1} | " + " | ".join(cells) + " |")
        allm = miss.all(axis=1)
        L += ["", f"Images missed by **every** model: {int(allm.sum())} of {len(W)} "
              f"({100 * allm.mean():.1f}%). By dataset: " +
              ", ".join(f"{d} {int(allm[W.index.get_level_values(0) == d].sum())}" for d in TRAINLIKE + UNSEEN), ""]
        W["mean_dice"] = W[models].mean(axis=1)
        hard = W.sort_values("mean_dice").head(25).reset_index().merge(an, on=["ds", "image"], how="left")
        hard[["ds", "image", "mean_dice", "area", "sharp", "dE_lab", "spec", "border"]].to_csv(
            os.path.join(a.out, "hardest_images.csv"), index=False)
        L += ["Hardest 25 images (lowest mean Dice across models) → `hardest_images.csv`", ""]
    open(os.path.join(a.out, "failure_report.md"), "w").write("\n".join(L))
    D.to_csv(os.path.join(a.out, "joined_per_image.csv"), index=False)
    print("\n".join(L))


if __name__ == "__main__":
    main()
