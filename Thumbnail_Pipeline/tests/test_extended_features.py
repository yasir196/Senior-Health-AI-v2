from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from Thumbnail_Pipeline.analyzer.features import analyze_image


def test_extended_features_are_bounded(tmp_path):
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(image, (40, 40), (600, 300), (255, 255, 255), -1)
    path = tmp_path / "extended.png"
    assert cv2.imwrite(str(path), image)
    result = analyze_image(path)

    assert len(result["dominant_colors_bgr"]) >= 1
    assert result["face_count"] >= 0
    assert 0 <= result["face_area_ratio"] <= 1
    assert 0 <= result["saliency_concentration"] <= 1
    assert 0 <= result["clutter_score"] <= 1
    assert 0 <= result["tiny_readability_edge_retention"] <= 2
