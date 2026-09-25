from pathlib import Path
import sys, pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from Thumbnail_Pipeline.io_policy import safe_output, OUTPUT_ROOT

def test_relative_output_stays_inside_pipeline_outputs():
    assert OUTPUT_ROOT in safe_output("intelligence/report.json").parents

def test_escape_is_rejected():
    with pytest.raises(ValueError):
        safe_output("../outside.json")
