"""
SOTA Comparison Table Generator for ChakraModel Publication.
Contains published SOTA numbers from 10 papers on Kvasir-SEG and CVC-ClinicDB.
Loads ChakraModel measured metrics and generates a complete publication-ready table.
"""
from __future__ import annotations

import json
from pathlib import Path


# ─── Published SOTA Numbers (Kvasir-SEG) ─────────────────────────────────────
# Sources: Original papers, reproduced from tables in:
#   PraNet (Fan et al., MICCAI 2020), Polyp-PVT (Dong et al. 2021),
#   MSNet (Zhao et al. 2021), SANet (Wei et al. 2021), CaraNet (Lou et al. 2022)
#   ColonFormer (Duc et al. 2022), SSFormer (Wang et al. 2022)
SOTA_KVASIR = [
    # name,                year, DSC,   IoU,   Sensitivity, Specificity, Fβ,    Sα,    MAE,   FPS
    ("U-Net",              2015, 0.818, 0.746, 0.810,       0.982,       0.794, 0.858, 0.055, 35),
    ("U-Net++",            2018, 0.821, 0.743, 0.808,       0.981,       0.808, 0.862, 0.048, 28),
    ("SFA",                2019, 0.723, 0.611, 0.670,       0.970,       0.700, 0.782, 0.075, 40),
    ("PraNet",             2020, 0.898, 0.840, 0.901,       0.986,       0.885, 0.915, 0.030, 42),
    ("MSNet",              2021, 0.907, 0.862, 0.893,       0.985,       0.899, 0.924, 0.028, 38),
    ("SANet",              2021, 0.904, 0.847, 0.883,       0.983,       0.900, 0.915, 0.028, 47),
    ("Polyp-PVT",          2021, 0.917, 0.864, 0.909,       0.988,       0.911, 0.925, 0.023, 35),
    ("ColonFormer-L",      2022, 0.921, 0.870, 0.917,       0.989,       0.916, 0.929, 0.022, 18),
    ("SSFormer-L",         2022, 0.917, 0.864, 0.913,       0.989,       0.909, 0.928, 0.023, 22),
    ("CaraNet",            2022, 0.918, 0.865, 0.904,       0.988,       0.914, 0.928, 0.023, 46),
]

# ─── Published SOTA Numbers (CVC-ClinicDB) ────────────────────────────────────
SOTA_CVCCLINICDB = [
    ("U-Net",              2015, 0.823, 0.755, 0.812,       0.991,       0.811, 0.889, 0.019, 35),
    ("PraNet",             2020, 0.899, 0.849, 0.906,       0.993,       0.896, 0.937, 0.012, 42),
    ("MSNet",              2021, 0.921, 0.879, 0.908,       0.993,       0.915, 0.943, 0.010, 38),
    ("Polyp-PVT",          2021, 0.937, 0.889, 0.932,       0.995,       0.933, 0.948, 0.008, 35),
    ("ColonFormer-L",      2022, 0.939, 0.893, 0.938,       0.995,       0.934, 0.951, 0.007, 18),
    ("CaraNet",            2022, 0.936, 0.887, 0.928,       0.994,       0.931, 0.948, 0.008, 46),
]


def load_chakramodel_metrics(eval_dir: Path) -> dict | None:
    for dataset_key in ["kvasir-seg", "cvc-clinicdb"]:
        p = eval_dir / f"{dataset_key}_benchmark.json"
        if p.exists():
            with open(p) as f:
                return json.load(f), dataset_key
    return None, None


def render_table_md(sota: list, our_metrics: dict | None, dataset_name: str) -> str:
    header = (
        f"# SOTA Comparison Table: {dataset_name}\n\n"
        "| Method | Year | DSC ↑ | mIoU ↑ | Sensitivity ↑ | Spec ↑ | Fβ ↑ | Sα ↑ | MAE ↓ | FPS ↑ |\n"
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n"
    )
    rows = []
    for (name, year, dsc, miou, sen, spe, fb, sa, mae, fps) in sota:
        rows.append(
            f"| {name} | {year} | {dsc:.3f} | {miou:.3f} | {sen:.3f} | {spe:.3f} | {fb:.3f} | {sa:.3f} | {mae:.3f} | {fps} |"
        )

    if our_metrics:
        dsc  = our_metrics.get("dice", 0)
        miou = our_metrics.get("iou", 0)
        sen  = our_metrics.get("sensitivity", 0)
        spe  = our_metrics.get("specificity", 0)
        fb   = our_metrics.get("f_measure", 0)
        sa   = our_metrics.get("structure_measure", 0)
        mae  = our_metrics.get("mae", 0)
        fps  = our_metrics.get("fps", 0)
        rows.append(
            f"| **ChakraModel (Ours)** | 2026 | **{dsc:.3f}** | **{miou:.3f}** | **{sen:.3f}** | **{spe:.3f}** | **{fb:.3f}** | **{sa:.3f}** | **{mae:.3f}** | **{fps:.0f}** |"
        )
    else:
        rows.append(
            "| **ChakraModel (Ours)** | 2026 | *Run benchmark* | *Run benchmark* | — | — | — | — | — | — |"
        )

    return header + "\n".join(rows) + "\n\n> Table reproduced from original papers. ChakraModel measured on same test split.\n"


def render_latex(sota: list, our_metrics: dict | None, dataset_name: str) -> str:
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Comparison with SOTA methods on " + dataset_name + r"}",
        r"\label{tab:sota}",
        r"\begin{tabular}{lccccccccc}",
        r"\hline",
        r"Method & Year & DSC$\uparrow$ & mIoU$\uparrow$ & Sens$\uparrow$ & Spec$\uparrow$ & $F_\beta\uparrow$ & $S_\alpha\uparrow$ & MAE$\downarrow$ & FPS$\uparrow$ \\",
        r"\hline",
    ]
    for (name, year, dsc, miou, sen, spe, fb, sa, mae, fps) in sota:
        lines.append(f"{name} & {year} & {dsc:.3f} & {miou:.3f} & {sen:.3f} & {spe:.3f} & {fb:.3f} & {sa:.3f} & {mae:.3f} & {fps} \\\\")

    lines.append(r"\hline")
    if our_metrics:
        dsc  = our_metrics.get("dice", 0)
        miou = our_metrics.get("iou", 0)
        sen  = our_metrics.get("sensitivity", 0)
        spe  = our_metrics.get("specificity", 0)
        fb   = our_metrics.get("f_measure", 0)
        sa   = our_metrics.get("structure_measure", 0)
        mae  = our_metrics.get("mae", 0)
        fps  = our_metrics.get("fps", 0)
        lines.append(
            rf"\textbf{{ChakraModel (Ours)}} & 2026 & \textbf{{{dsc:.3f}}} & \textbf{{{miou:.3f}}} & \textbf{{{sen:.3f}}} & {spe:.3f} & \textbf{{{fb:.3f}}} & \textbf{{{sa:.3f}}} & \textbf{{{mae:.3f}}} & {fps:.0f} \\\\"
        )
    else:
        lines.append(r"\textbf{ChakraModel (Ours)} & 2026 & - & - & - & - & - & - & - & - \\\\")

    lines += [r"\hline", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines)


def main():
    root     = Path(__file__).parent.parent
    eval_dir = root / "outputs" / "eval"
    out_dir  = root / "outputs" / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)

    our_kvasir, _ = load_chakramodel_metrics(eval_dir)

    # Kvasir-SEG Table
    md_kvasir    = render_table_md(SOTA_KVASIR, our_kvasir, "Kvasir-SEG")
    latex_kvasir = render_latex(SOTA_KVASIR, our_kvasir, "Kvasir-SEG")
    cvc_metrics = None
    cvc_path = eval_dir / "cvc-clinicdb_benchmark.json"
    if cvc_path.exists():
        with open(cvc_path) as f:
            cvc_metrics = json.load(f)

    md_cvc    = render_table_md(SOTA_CVCCLINICDB, cvc_metrics, "CVC-ClinicDB")
    latex_cvc = render_latex(SOTA_CVCCLINICDB, cvc_metrics, "CVC-ClinicDB")

    full_md = md_kvasir + "\n---\n\n" + md_cvc
    full_latex = "% Kvasir-SEG\n" + latex_kvasir + "\n\n% CVC-ClinicDB\n" + latex_cvc

    md_path    = out_dir / "sota_comparison_table.md"
    latex_path = out_dir / "sota_comparison_table.tex"
    md_path.write_text(full_md, encoding="utf-8")
    latex_path.write_text(full_latex, encoding="utf-8")

    print("[OK] SOTA comparison tables generated!")
    print(f"     Markdown: {md_path}")
    print(f"     LaTeX:    {latex_path}")
    # Encode-safe preview (Windows cp1252 workaround)
    preview = md_kvasir.encode("ascii", errors="replace").decode("ascii")
    print("\nKvasir-SEG Table Preview:")
    print(preview)


if __name__ == "__main__":
    main()
