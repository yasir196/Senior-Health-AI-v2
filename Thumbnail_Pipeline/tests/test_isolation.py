from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from Thumbnail_Pipeline.analyzer.run import OUTPUT_ROOT, _safe_output


def test_output_root_is_inside_thumbnail_pipeline():
    assert "Thumbnail_Pipeline" in OUTPUT_ROOT.parts
    assert OUTPUT_ROOT.name == "outputs"


def test_rejects_write_outside_output_root():
    forbidden = ROOT.parent / "config.json"
    try:
        _safe_output(forbidden)
    except ValueError:
        return
    raise AssertionError("V2 write boundary was not enforced")
