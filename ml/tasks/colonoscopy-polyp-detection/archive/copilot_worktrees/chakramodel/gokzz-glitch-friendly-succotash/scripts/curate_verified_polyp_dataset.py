"""Create a non-destructive, Kaggle-ready snapshot from the verified PraNet data.

The source project and all archives remain untouched. The output contains:
  train: 1232 pairs
  val: 218 pairs
  test/<dataset>: 798 pairs across five external test sets
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path


DATASETS = {
    "kvasir": ("Kvasir", "test_kvasir.tsv"),
    "clinicdb": ("CVC-ClinicDB", "test_cvc_clinicdb.tsv"),
    "colondb": ("CVC-ColonDB", "test_cvc_colondb.tsv"),
    "etis": ("ETIS-LaribPolypDB", "test_etis_laribpolypdb.tsv"),
    "cvc300": ("CVC-300", "test_cvc_300.tsv"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path) -> list[tuple[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle, delimiter="\t")
        return [(row["image"], row["mask"]) for row in rows]


def resolve(root: Path, value: str) -> Path:
    return root / Path(value.replace("\\", "/"))


def copy_pair(
    image: Path,
    mask: Path,
    output_root: Path,
    split: str,
    name: str,
    rows: list[dict],
) -> None:
    image_out = output_root / split / "images" / f"{name}{image.suffix.lower()}"
    mask_out = output_root / split / "masks" / f"{name}.png"
    image_out.parent.mkdir(parents=True, exist_ok=True)
    mask_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(image, image_out)
    shutil.copy2(mask, mask_out)
    rows.append(
        {
            "image": str(image_out.relative_to(output_root)).replace("\\", "/"),
            "mask": str(mask_out.relative_to(output_root)).replace("\\", "/"),
            "source_image": str(image),
            "source_mask": str(mask),
            "image_sha256": sha256(image),
            "mask_sha256": sha256(mask),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(r"M:\chakramodelpro\polyp-detection-research"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"M:\chakramodelpro\kaggle_ready_polyp_segmentation_v1"),
    )
    args = parser.parse_args()
    project = args.project_root
    output = args.output_root
    manifests = project / "data" / "processed" / "manifests"
    raw = project / "data" / "raw" / "pranet_benchmark"
    cleaned_masks = project / "data" / "processed" / "cleaned_masks"

    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")

    rows_by_split: dict[str, list[dict]] = defaultdict(list)
    missing: list[dict] = []

    for split, manifest_name in (("train", "train_pranet_train.tsv"), ("val", "val_pranet.tsv")):
        for image_value, mask_value in read_manifest(manifests / manifest_name):
            image = resolve(project, image_value)
            mask = resolve(project, mask_value)
            if not image.is_file() or not mask.is_file():
                missing.append({"split": split, "image": str(image), "mask": str(mask)})
                continue
            stem = Path(image_value.replace("\\", "/")).stem
            copy_pair(image, mask, output, split, f"train_{stem}", rows_by_split[split])

    for dataset_key, (dataset_name, manifest_name) in DATASETS.items():
        for image_value, mask_value in read_manifest(manifests / manifest_name):
            image = resolve(project, image_value)
            # External test manifests point to raw benchmark masks. Keep these
            # original validated masks separate from the cleaned training masks.
            mask = resolve(project, mask_value)
            if not image.is_file() or not mask.is_file():
                missing.append(
                    {
                        "split": f"test/{dataset_key}",
                        "image": str(image),
                        "mask": str(mask),
                    }
                )
                continue
            stem = Path(image_value.replace("\\", "/")).stem
            rows_by_split[f"test/{dataset_key}"].append(
                {
                    "dataset": dataset_name,
                    "source_image": str(image),
                    "source_mask": str(mask),
                    "image_sha256": sha256(image),
                    "mask_sha256": sha256(mask),
                }
            )
            copy_pair(
                image,
                mask,
                output,
                f"test/{dataset_key}",
                f"{dataset_key}_{stem}",
                rows_by_split[f"test/{dataset_key}"],
            )
            # copy_pair appends the complete row; remove the pre-recorded row.
            rows_by_split[f"test/{dataset_key}"].pop(-2)

    duplicate_masks: dict[str, list[str]] = defaultdict(list)
    for split, rows in rows_by_split.items():
        manifest_path = output / f"{split.replace('/', '_')}.tsv"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", newline="", encoding="utf-8") as handle:
            fields = ["image", "mask", "source_image", "source_mask", "image_sha256", "mask_sha256"]
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fields})
                duplicate_masks[row["mask_sha256"]].append(f"{split}:{row['source_mask']}")

    duplicate_groups = [members for members in duplicate_masks.values() if len(members) > 1]
    report = {
        "output_root": str(output),
        "source_project": str(project),
        "counts": {split: len(rows) for split, rows in sorted(rows_by_split.items())},
        "total_pairs": sum(len(rows) for rows in rows_by_split.values()),
        "missing_pairs": missing,
        "duplicate_mask_groups": duplicate_groups,
        "training_policy": {
            "approved_training_splits": ["train", "val"],
            "external_test_only": sorted(k for k in rows_by_split if k.startswith("test/")),
            "videos_included": False,
            "incomplete_archives_included": False,
        },
        "source_notes": [
            "Train and validation masks come from the validated cleaned_masks snapshot.",
            "External test masks are copied from the validated PraNet benchmark.",
            "Duplicate masks are retained and reported; no samples were silently deleted.",
        ],
    }
    (output / "curation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (output / "README.txt").write_text(
        "Kaggle-ready polyp segmentation snapshot\n"
        "=========================================\n"
        f"Total image-mask pairs: {report['total_pairs']}\n"
        f"Training pairs: {len(rows_by_split['train'])}\n"
        f"Validation pairs: {len(rows_by_split['val'])}\n"
        "External test sets are kept separate and must not be used for training.\n"
        "See curation_report.json for hashes, source paths, missing files, and duplicates.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
