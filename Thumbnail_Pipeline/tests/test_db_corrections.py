from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from Thumbnail_Pipeline.db.store import EDITABLE_FIELDS

def test_required_human_edit_fields_exist():
    assert "thumbnail_text_observed" in EDITABLE_FIELDS
    assert "title_observed" in EDITABLE_FIELDS
    assert "pattern_inferred" in EDITABLE_FIELDS
    assert "category_inferred" in EDITABLE_FIELDS
    assert "ctr_observed" in EDITABLE_FIELDS
    assert "impressions_observed" in EDITABLE_FIELDS
