from __future__ import annotations

import argparse
import json
from pathlib import Path

from .features import analyze_image


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = (PIPELINE_ROOT / "outputs").resolve()


def _safe_output(path: Path) -> Path:
    resolved = path.resolve()
    if resolved != OUTPUT_ROOT and OUTPUT_ROOT not in resolved.parents:
        raise ValueError("Writes outside Thumbnail_Pipeline/outputs are forbidden")
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze one historical thumbnail")
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", default="thumbnail_features.json")
    args = parser.parse_args()

    output = _safe_output(OUTPUT_ROOT / args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": "0.1.0",
        "source": str(args.image),
        "features": analyze_image(args.image),
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
