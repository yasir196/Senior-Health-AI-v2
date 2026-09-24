from __future__ import annotations

from collections import Counter
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
    dominant_colors_bgr: list[list[int]]
    face_count: int
    face_boxes_normalized: list[list[float]]
    face_area_ratio: float
    saliency_concentration: float
    clutter_score: float
    tiny_readability_edge_retention: float


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _edge_map(gray: np.ndarray) -> np.ndarray:
    return cv2.Canny(gray, 100, 200)


def _dominant_colors(image: np.ndarray, k: int = 5) -> list[list[int]]:
    small = cv2.resize(image, (160, 90), interpolation=cv2.INTER_AREA)
    pixels = small.reshape((-1, 3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0)
    _compactness, labels, centers = cv2.kmeans(
        pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS
    )
    counts = Counter(labels.flatten().tolist())
    order = [idx for idx, _ in counts.most_common()]
    return [[int(v) for v in centers[idx]] for idx in order]


def _faces(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        return []
    found = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    return [tuple(int(v) for v in box) for box in found]


def _saliency_concentration(gray: np.ndarray) -> float:
    # Spectral-residual style proxy without opencv-contrib dependency:
    # local contrast energy concentrated in the strongest 10% of pixels.
    blur = cv2.GaussianBlur(gray, (0, 0), 7)
    residual = cv2.absdiff(gray, blur).astype(np.float32)
    total = float(residual.sum())
    if total == 0:
        return 0.0
    threshold = float(np.percentile(residual, 90))
    strong = float(residual[residual >= threshold].sum())
    return round(strong / total, 6)


def _tiny_edge_retention(gray: np.ndarray, target_width: int = 168) -> float:
    full = _edge_map(gray)
    full_density = float(np.mean(full > 0))
    if full_density == 0:
        return 1.0
    target_height = max(1, round(gray.shape[0] * target_width / gray.shape[1]))
    tiny = cv2.resize(gray, (target_width, target_height), interpolation=cv2.INTER_AREA)
    tiny_density = float(np.mean(_edge_map(tiny) > 0))
    return round(min(tiny_density / full_density, 2.0), 6)


def analyze_image(path: str | Path) -> dict[str, Any]:
    """Extract deterministic, local-only visual features from one thumbnail."""
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

    y0 = int(height * 0.78)
    x0 = int(width * 0.78)
    safe_edges = edges[y0:height, x0:width]

    faces = _faces(gray)
    normalized_faces: list[list[float]] = []
    face_pixels = 0
    for x, y, w, h in faces:
        normalized_faces.append([
            round(x / width, 6), round(y / height, 6),
            round(w / width, 6), round(h / height, 6),
        ])
        face_pixels += w * h

    edge_density = float(np.mean(edges > 0))
    occupied_cells = sum(1 for value in cells if value > 0.035)
    clutter = min(1.0, (edge_density / 0.18) * 0.65 + (occupied_cells / 9) * 0.35)

    features = ThumbnailFeatures(
        width=width,
        height=height,
        aspect_ratio=round(width / height, 6),
        brightness_mean=round(float(np.mean(gray)), 4),
        contrast_std=round(float(np.std(gray)), 4),
        edge_density=round(edge_density, 6),
        dark_pixel_ratio=round(float(np.mean(gray < 48)), 6),
        thirds_occupancy=cells,
        timestamp_safe_zone_edge_density=round(float(np.mean(safe_edges > 0)), 6),
        dominant_colors_bgr=_dominant_colors(image),
        face_count=len(faces),
        face_boxes_normalized=normalized_faces,
        face_area_ratio=round(face_pixels / (width * height), 6),
        saliency_concentration=_saliency_concentration(gray),
        clutter_score=round(clutter, 6),
        tiny_readability_edge_retention=_tiny_edge_retention(gray),
    )
    return asdict(features)
