from __future__ import annotations

import csv
import json
from pathlib import Path

from .features import analyze_image
from .ocr import analyze_text

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}


def analyze_folder(source: Path, output_jsonl: Path, output_csv: Path) -> int:
    images = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    rows = []
    with output_jsonl.open("w", encoding="utf-8") as stream:
        for image in images:
            payload = {
                "source": str(image),
                "features": analyze_image(image),
                "ocr": analyze_text(image),
            }
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
            f = payload["features"]
            rows.append({
                "source": str(image),
                "width": f["width"],
                "height": f["height"],
                "brightness_mean": f["brightness_mean"],
                "contrast_std": f["contrast_std"],
                "edge_density": f["edge_density"],
                "dark_pixel_ratio": f["dark_pixel_ratio"],
                "face_count": f["face_count"],
                "face_area_ratio": f["face_area_ratio"],
                "saliency_concentration": f["saliency_concentration"],
                "clutter_score": f["clutter_score"],
                "tiny_readability_edge_retention": f["tiny_readability_edge_retention"],
                "ocr_word_count": payload["ocr"].get("word_count"),
                "ocr_line_count": payload["ocr"].get("line_count"),
            })

    fieldnames = list(rows[0].keys()) if rows else ["source"]
    with output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
