from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2


def analyze_text(path: str | Path) -> dict[str, Any]:
    """Optional OCR. Core analyzer remains usable without Tesseract installed."""
    try:
        import pytesseract
    except ImportError:
        return {"available": False, "reason": "pytesseract_not_installed"}

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Could not read image: {path}")

    try:
        data = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT, config="--psm 11"
        )
    except pytesseract.TesseractNotFoundError:
        return {"available": False, "reason": "tesseract_binary_not_found"}
    except Exception as exc:
        return {"available": False, "reason": "ocr_runtime_error", "detail": str(exc)}

    words = []
    boxes = []
    line_keys = set()
    height, width = image.shape[:2]
    for i, raw in enumerate(data["text"]):
        word = raw.strip()
        try:
            confidence = float(data["conf"][i])
        except (TypeError, ValueError):
            confidence = -1
        if not word or confidence < 30:
            continue
        words.append(word)
        x, y, w, h = (int(data[key][i]) for key in ("left", "top", "width", "height"))
        boxes.append([round(x/width,6), round(y/height,6), round(w/width,6), round(h/height,6)])
        line_keys.add((data["block_num"][i], data["par_num"][i], data["line_num"][i]))

    return {
        "available": True,
        "text": " ".join(words),
        "word_count": len(words),
        "line_count": len(line_keys),
        "boxes_normalized": boxes,
        "text_area_ratio": round(sum(b[2] * b[3] for b in boxes), 6),
    }
