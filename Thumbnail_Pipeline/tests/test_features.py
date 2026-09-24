from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from Thumbnail_Pipeline.analyzer.features import analyze_image


def test_basic_feature_extraction(tmp_path):
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[:, 640:] = 255
    path = tmp_path / "sample.png"
    assert cv2.imwrite(str(path), image)

    result = analyze_image(path)

    assert result["width"] == 1280
    assert result["height"] == 720
    assert abs(result["aspect_ratio"] - (16 / 9)) < 0.001
    assert len(result["thirds_occupancy"]) == 9
    assert 0 <= result["dark_pixel_ratio"] <= 1
