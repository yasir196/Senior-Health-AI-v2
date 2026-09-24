from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from Thumbnail_Pipeline.dashboard.schema import audit_record
from Thumbnail_Pipeline.dashboard.review import apply_human_review


def test_audit_record_keeps_full_text_and_source_metrics():
    r = audit_record({"asset_id":"a1","performance":{"title":"Chair title","ctr":6.2,"impressions":12000},"ocr":{"text":"KNEE PAIN? DO THIS FIRST"}})
    assert r["observed"]["thumbnail_text_full"] == "KNEE PAIN? DO THIS FIRST"
    assert r["observed"]["impressions"] == 12000


def test_human_correction_does_not_destroy_original():
    r = audit_record({"performance":{"title":"T","ctr":5,"impressions":2000},"ocr":{"text":"DO TH1S"}})
    u = apply_human_review(r, flags=["ocr_error"], corrections={"thumbnail_text_full":"DO THIS"})
    assert u["observed"]["thumbnail_text_full"] == "DO TH1S"
    assert u["human_review"]["corrections"]["thumbnail_text_full"] == "DO THIS"
