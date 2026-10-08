"""Dataset layout discovery and dependency-free validators."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def _files(root: Path, suffixes: set[str]) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def _pair_report(images: list[Path], labels: list[Path], label_suffixes: set[str]) -> dict[str, Any]:
    image_stems = {path.stem for path in images}
    label_stems = {path.stem for path in labels}
    return {
        "images": len(images),
        "labels": len(labels),
        "missing_labels": sorted(image_stems - label_stems),
        "orphan_labels": sorted(label_stems - image_stems),
        "label_suffixes": sorted(label_suffixes),
    }


def validate_yolo(root: Path) -> dict[str, Any]:
    images = _files(root, IMAGE_SUFFIXES)
    labels = _files(root, {".txt"})
    malformed: list[dict[str, Any]] = []
    for label in labels:
        try:
            for line_number, line in enumerate(label.read_text(encoding="utf-8").splitlines(), 1):
                parts = line.split()
                if len(parts) not in (5, 6):
                    raise ValueError("expected class plus four box coordinates")
                values = [float(value) for value in parts[1:]]
                if any(value < 0 or value > 1 for value in values):
                    raise ValueError("normalized coordinates must be between 0 and 1")
        except (OSError, UnicodeError, ValueError) as exc:
            malformed.append({"path": str(label.relative_to(root).as_posix()),
                              "error": f"{type(exc).__name__}: {exc}"})
    result = _pair_report(images, labels, {".txt"})
    result.update({"layout": "yolo", "malformed_annotations": malformed})
    return result


def validate_coco(root: Path) -> dict[str, Any]:
    candidates = sorted(root.rglob("*.json"))
    found = None
    malformed: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and {"images", "annotations", "categories"} <= set(payload):
                found = candidate
                break
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            malformed.append({"path": candidate.relative_to(root).as_posix(),
                              "error": f"{type(exc).__name__}: {exc}"})
    if found is None:
        return {"layout": "coco", "found": False, "malformed_annotations": malformed}
    payload = json.loads(found.read_text(encoding="utf-8"))
    required = {"id", "file_name"}
    bad_images = [item for item in payload["images"] if not required <= set(item)]
    bad_annotations = [item for item in payload["annotations"]
                       if not {"id", "image_id", "category_id"} <= set(item)]
    malformed.extend({"path": found.relative_to(root).as_posix(), "error": detail}
                     for detail in (["image entries missing id/file_name"] if bad_images else [])
                     + (["annotation entries missing id/image_id/category_id"] if bad_annotations else []))
    return {"layout": "coco", "found": True, "annotation_file": found.relative_to(root).as_posix(),
            "images": len(payload["images"]), "annotations": len(payload["annotations"]),
            "categories": len(payload["categories"]), "malformed_annotations": malformed}


def discover_dataset(root: str) -> dict[str, Any]:
    """Detect common layouts and return validation findings."""
    path = Path(root).expanduser().resolve()
    images = _files(path, IMAGE_SUFFIXES) if path.is_dir() else []
    reserved = {"images", "labels", "annotations", "masks", "mask", "annotations"}
    class_dirs = sorted({
        image.parent for image in images
        if image.parent != path and image.parent.parent == path
        and image.parent.name.casefold() not in reserved
    })
    class_folder = bool(class_dirs) and all(any(child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES
                                                for child in directory.iterdir())
                                            for directory in class_dirs)
    label_dirs = [candidate for candidate in path.rglob("*") if candidate.is_dir()
                  and candidate.name.casefold() in {"labels", "annotations"}]
    mask_dirs = [candidate for candidate in path.rglob("*") if candidate.is_dir()
                 and candidate.name.casefold() in {"masks", "mask"}]
    image_label = any(_files(directory, {".txt", ".json", ".xml"}) for directory in label_dirs)
    image_mask = any(_files(directory, IMAGE_SUFFIXES) for directory in mask_dirs)
    yolo = validate_yolo(path) if (
        any(image.suffix.lower() == ".txt" for image in path.rglob("*.txt"))
        or any(directory.name.casefold() == "labels" for directory in path.rglob("*") if directory.is_dir())
    ) else None
    coco = validate_coco(path)
    layouts = []
    if class_folder:
        layouts.append("class-folder")
    if yolo:
        layouts.append("yolo")
    if coco.get("found"):
        layouts.append("coco")
    if image_label:
        layouts.append("image-label")
    if image_mask:
        layouts.append("image-mask")
    return {
        "root": str(path),
        "layouts": layouts,
        "class_folder": {"classes": sorted(directory.name for directory in class_dirs)} if class_folder else None,
        "yolo": yolo,
        "coco": coco,
        "image_label": {"label_directories": [str(item.relative_to(path).as_posix()) for item in label_dirs]}
        if image_label else None,
        "image_mask": {"mask_directories": [str(item.relative_to(path).as_posix()) for item in mask_dirs]}
        if image_mask else None,
    }
