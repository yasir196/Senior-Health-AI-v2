from __future__ import annotations
from typing import Any


def audit_record(row: dict[str, Any], analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    perf, ocr = row.get("performance") or {}, row.get("ocr") or {}
    return {
        "source": {
            "asset_id": row.get("asset_id"),
            "thumbnail_path": row.get("thumbnail_path") or row.get("path"),
        },
        "observed": {
            "title": perf.get("title"),
            "ctr": perf.get("ctr"),
            "impressions": perf.get("impressions"),
            "video_id": perf.get("video_id"),
            "upload_date": perf.get("upload_date"),
        },
        "extracted": {"thumbnail_text_full": ocr.get("text"), "ocr_available": ocr.get("available")},
        "inferred": analysis or {},
        "human_review": {
            "status": "unreviewed",
            "flags": [],
            "corrections": {},
            "notes": "",
        },
        "provenance": {
            "observed_is_source_data": True,
            "extracted_is_machine_extracted": True,
            "inferred_is_analyzer_output": True,
            "human_corrections_preserve_original": True,
        },
    }


ALLOWED_FLAGS = (
    "ocr_error",
    "wrong_pattern",
    "wrong_category",
    "wrong_title_pair",
    "wrong_performance_match",
    "wrong_visual_detection",
    "other",
)
