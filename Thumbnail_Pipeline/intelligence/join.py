from __future__ import annotations

from collections import defaultdict
from typing import Any


def join_by_asset_id(
    feature_rows: list[dict[str, Any]],
    performance_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join analyzer output to performance without writing to V2."""
    performance = defaultdict(list)
    for row in performance_rows:
        key = row.get("asset_id")
        if key:
            performance[str(key)].append(row)

    joined: list[dict[str, Any]] = []
    for feature in feature_rows:
        key = str(feature.get("asset_id") or "")
        matches = performance.get(key) or [None]
        for perf in matches:
            joined.append({
                **feature,
                "performance": perf,
                "performance_match": perf is not None,
            })
    return joined
