from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ALIASES = {
    "asset_id": ("asset_id", "project_id", "id"),
    "video_id": ("video_id", "youtube_video_id"),
    "title": ("title", "video_title"),
    "ctr": ("ctr", "impressions_ctr", "impressions_click_through_rate"),
    "impressions": ("impressions",),
    "views": ("views",),
    "watch_time": ("watch_time", "watch_time_hours", "estimated_minutes_watched"),
    "avd": ("avd", "average_view_duration", "average_view_duration_seconds"),
    "upload_date": ("upload_date", "published_at", "published_date"),
}


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    result: dict[str, Any] = {}
    for canonical, aliases in ALIASES.items():
        result[canonical] = next((lowered[a] for a in aliases if a in lowered), None)
    return result


def read_performance_export(path: Path) -> list[dict[str, Any]]:
    """Read a V2 performance export without modifying it.

    CSV and JSON/JSONL are supported so this adapter is not coupled to V2's
    internal database implementation.
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return [_normalize(dict(row)) for row in csv.DictReader(stream)]
    if suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as stream:
            return [_normalize(json.loads(line)) for line in stream if line.strip()]
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("rows", [])
        return [_normalize(dict(row)) for row in rows]
    raise ValueError(f"Unsupported performance export: {path}")
