from __future__ import annotations
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = (PIPELINE_ROOT / "outputs").resolve()

def safe_output(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = OUTPUT_ROOT / candidate
    resolved = candidate.resolve()
    if resolved != OUTPUT_ROOT and OUTPUT_ROOT not in resolved.parents:
        raise ValueError(f"Thumbnail Pipeline output must stay inside {OUTPUT_ROOT}")
    return resolved
