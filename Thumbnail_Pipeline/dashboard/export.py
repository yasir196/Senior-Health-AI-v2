from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from Thumbnail_Pipeline.io_policy import safe_output


def export_dashboard_payload(records: list[dict[str, Any]], summary: dict[str, Any], output: str = "dashboard/audit_dashboard.json") -> Path:
    path = safe_output(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dashboard_version": "0.1.0",
        "summary": summary,
        "records": records,
        "legend": {
            "OBSERVED": "Direct source data such as title, OCR text, CTR and impressions.",
            "INFERRED": "Analyzer classification or derived pattern.",
            "HUMAN_CORRECTED": "Explicit review overlay; original evidence remains visible.",
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
