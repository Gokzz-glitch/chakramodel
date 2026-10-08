"""Independent, read-only cross-check for the polyp research dataset.

This deliberately does not import or call the project's integrity/overlay
scripts. It recomputes their core claims from manifests and file bytes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image


MANIFESTS = {
    "train_pranet_train.tsv": 1232,
    "val_pranet.tsv": 218,
    "test_kvasir.tsv": 100,
    "test_cvc_clinicdb.tsv": 62,
    "test_cvc_colondb.tsv": 380,
    "test_etis_laribpolypdb.tsv": 196,
    "test_cvc_300.tsv": 60,
}


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def same_bytes(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as left_handle, right.open("rb") as right_handle:
        while True:
            left_chunk = left_handle.read(4 * 1024 * 1024)
            right_chunk = right_handle.read(4 * 1024 * 1024)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def add_failure(failures: list[dict[str, Any]], gate: str, **details: Any) -> None:
    failures.append({"gate": gate, **details})


def load_manifest(path: Path, expected: int, failures: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not path.is_file():
        add_failure(failures, "missing_manifest", path=str(path))
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != expected:
        add_failure(failures, "manifest_count", path=str(path), expected=expected, actual=len(rows))
    if rows and set(rows[0]) != {"image", "mask"}:
        add_failure(failures, "manifest_columns", path=str(path), columns=sorted(rows[0]))
    return rows


def latest_report(directory: Path, pattern: str) -> Path | None:
    reports = sorted(directory.glob(pattern), key=lambda item: item.stat().st_mtime)
    return reports[-1] if reports else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    manifest_root = root / "data" / "processed" / "manifests"
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    records: dict[str, dict[str, Any]] = {}
    split_paths: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"image": [], "mask": []})
    total_bytes = 0

    config = root / "configs" / "baseline_unet.yaml"
    if not config.is_file():
        add_failure(failures, "missing_config", path=str(config))
    else:
        config_text = config.read_text(encoding="utf-8")
        for required in ("train_pranet_train.tsv", "val_pranet.tsv"):
            if required not in config_text:
                add_failure(failures, "config_reference", expected=required, path=str(config))
        if "test_kvasir.tsv" in config_text and "val_manifest" in config_text:
            val_line = next((line for line in config_text.splitlines() if "val_manifest" in line), "")
            if "test_kvasir.tsv" in val_line:
                add_failure(failures, "validation_uses_test_manifest", line=val_line)

    manifests: dict[str, list[dict[str, str]]] = {}
    for name, expected in MANIFESTS.items():
        rows = load_manifest(manifest_root / name, expected, failures)
        manifests[name] = rows
        role = Path(name).stem
        for row_number, row in enumerate(rows, start=2):
            for kind in ("image", "mask"):
                relative = row.get(kind, "")
                target = (root / relative).resolve()
                split_paths[role][kind].append(str(target))
                if not target.is_file():
                    add_failure(
                        failures,
                        "missing_target",
                        manifest=name,
                        row=row_number,
                        kind=kind,
                        path=str(target),
                    )
                    continue
                key = str(target).lower()
                if key in records and records[key]["kind"] != kind:
                    add_failure(failures, "same_path_used_as_image_and_mask", path=str(target))
                    continue
                if key in records:
                    continue
                record: dict[str, Any] = {"path": str(target), "kind": kind}
                try:
                    digest, size = sha256_file(target)
                    record.update({"sha256": digest, "bytes": size})
                    total_bytes += size
                    with Image.open(target) as image:
                        image.load()
                        record["dimensions"] = list(image.size)
                        record["mode"] = image.mode
                        if kind == "mask":
                            values = set(image.convert("L").getdata())
                            record["mask_values"] = sorted(values)
                            if not values.issubset({0, 255}):
                                add_failure(
                                    failures,
                                    "non_binary_mask",
                                    path=str(target),
                                    values=sorted(values)[:50],
                                )
                except Exception as exc:
                    add_failure(failures, "unreadable_file", kind=kind, path=str(target), error=str(exc))
                records[key] = record

            image_path = root / row.get("image", "")
            mask_path = root / row.get("mask", "")
            if image_path.is_file() and mask_path.is_file():
                try:
                    with Image.open(image_path) as image, Image.open(mask_path) as mask:
                        if image.size != mask.size:
                            add_failure(
                                failures,
                                "dimension_mismatch",
                                manifest=name,
                                row=row_number,
                                image=str(image_path),
                                mask=str(mask_path),
                                image_size=list(image.size),
                                mask_size=list(mask.size),
                            )
                except Exception:
                    pass

    digest_groups: dict[tuple[str, int, str], list[str]] = defaultdict(list)
    for record in records.values():
        if "sha256" in record:
            digest_groups[(record["sha256"], record["bytes"], record["kind"])].append(record["path"])

    duplicate_groups = []
    for (digest, size, kind), paths in digest_groups.items():
        if len(paths) < 2:
            continue
        confirmed = all(same_bytes(Path(paths[0]), Path(path)) for path in paths[1:])
        duplicate_groups.append({"sha256": digest, "bytes": size, "kind": kind, "paths": paths, "byte_confirmed": confirmed})
        if not confirmed:
            add_failure(failures, "hash_collision_or_changed_file", sha256=digest, paths=paths)

    split_digests: dict[str, dict[str, set[tuple[str, int]]]] = defaultdict(lambda: {"image": set(), "mask": set()})
    for role, kinds in split_paths.items():
        for kind, paths in kinds.items():
            for path in paths:
                record = records.get(path.lower())
                if record and "sha256" in record:
                    split_digests[role][kind].add((record["sha256"], record["bytes"]))

    roles = sorted(split_digests)
    cross_split_overlaps = []
    for index, left in enumerate(roles):
        for right in roles[index + 1:]:
            for kind in ("image", "mask"):
                overlap = split_digests[left][kind] & split_digests[right][kind]
                if overlap:
                    cross_split_overlaps.append({"left": left, "right": right, "kind": kind, "count": len(overlap)})
                    add_failure(failures, "cross_split_duplicate", left=left, right=right, kind=kind, count=len(overlap))

    overlay_dir = root / "results" / "overlays"
    overlay_report_path = latest_report(overlay_dir, "overlay_audit_*.json")
    overlay_summary: dict[str, Any] = {"report": str(overlay_report_path) if overlay_report_path else None}
    if overlay_report_path:
        try:
            overlay = json.loads(overlay_report_path.read_text(encoding="utf-8"))
            entries = overlay.get("results", overlay.get("images", []))
            if isinstance(entries, dict):
                entries = list(entries.values())
            missing_overlay_paths = []
            for entry in entries if isinstance(entries, list) else []:
                candidate = entry.get("path") or entry.get("image_path") or entry.get("image")
                if candidate and not Path(candidate).is_file():
                    candidate_path = root / candidate
                    if not candidate_path.is_file():
                        missing_overlay_paths.append(str(candidate))
            overlay_summary.update({"entry_count": len(entries) if isinstance(entries, list) else None, "missing_paths": missing_overlay_paths})
            if missing_overlay_paths:
                add_failure(failures, "overlay_report_missing_path", count=len(missing_overlay_paths), sample=missing_overlay_paths[:10])
        except Exception as exc:
            add_failure(failures, "overlay_report_unreadable", path=str(overlay_report_path), error=str(exc))
    else:
        warnings.append({"gate": "overlay_report_missing"})

    output_dir = root / "results" / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = output_dir / f"independent_crosscheck_{timestamp}.json"
    result = {
        "schema_version": 1,
        "project_root": str(root),
        "manifests": {name: len(rows) for name, rows in manifests.items()},
        "unique_files_hashed": len(records),
        "total_bytes_read": total_bytes,
        "duplicate_groups": duplicate_groups,
        "cross_split_overlaps": cross_split_overlaps,
        "overlay_report": overlay_summary,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "exit_code": 1 if failures else 0,
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": str(output),
        "unique_files_hashed": len(records),
        "total_bytes_read": total_bytes,
        "duplicate_groups": len(duplicate_groups),
        "cross_split_overlaps": len(cross_split_overlaps),
        "failures": len(failures),
        "warnings": len(warnings),
        "exit_code": result["exit_code"],
    }, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
