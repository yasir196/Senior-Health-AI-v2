from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class ThumbnailFeatures:
    width: int
    height: int
    aspect_ratio: float
    brightness_mean: float
    contrast_std: float
    edge_density: float
    dark_pixel_ratio: float
    thirds_occupancy: list[float]
    timestamp_safe_zone_edge_density: float


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _edge_map(gray: np.ndarray) -> np.ndarray:
    return cv2.Canny(gray, 100, 200)


def analyze_image(path: str | Path) -> dict[str, Any]:
    """Extract deterministic visual features from one thumbnail."""
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Could not read image: {path}")

    height, width = image.shape[:2]
    gray = _gray(image)
    edges = _edge_map(gray)

    cells: list[float] = []
    for row in range(3):
        for col in range(3):
            y0, y1 = row * height // 3, (row + 1) * height // 3
            x0, x1 = col * width // 3, (col + 1) * width // 3
            cell = edges[y0:y1, x0:x1]
            cells.append(round(float(np.mean(cell > 0)), 6))

    # YouTube timestamp commonly occupies the lower-right corner.
    y0 = int(height * 0.78)
    x0 = int(width * 0.78)
    safe_edges = edges[y0:height, x0:width]

    features = ThumbnailFeatures(
        width=width,
        height=height,
        aspect_ratio=round(width / height, 6),
        brightness_mean=round(float(np.mean(gray)), 4),
        contrast_std=round(float(np.std(gray)), 4),
        edge_density=round(float(np.mean(edges > 0)), 6),
        dark_pixel_ratio=round(float(np.mean(gray < 48)), 6),
        thirds_occupancy=cells,
        timestamp_safe_zone_edge_density=round(float(np.mean(safe_edges > 0)), 6),
    )
    return asdict(features)
