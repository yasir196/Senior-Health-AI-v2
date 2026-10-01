import csv
import json
from pathlib import Path

from production_ratio_controller import allocate_ratio_targets


def test_ratio_allocation_uses_duration_not_scene_count(tmp_path: Path) -> None:
    fields = ["slot_id","start_time","end_time","duration_sec","scope","source_segment_ids","transcript_text","rule_id","rule_priority","constraint_type","timing_source"]
    rows = [
        {"slot_id":"P0001","start_time":"0:00","end_time":"0:40","duration_sec":"40","scope":"BODY","source_segment_ids":"T1","transcript_text":"a","rule_id":"","rule_priority":"","constraint_type":"NONE","timing_source":"MASTER_TRANSCRIPT"},
        {"slot_id":"P0002","start_time":"0:40","end_time":"1:00","duration_sec":"20","scope":"BODY","source_segment_ids":"T2","transcript_text":"b","rule_id":"","rule_priority":"","constraint_type":"NONE","timing_source":"MASTER_TRANSCRIPT"},
        {"slot_id":"P0003","start_time":"1:00","end_time":"1:20","duration_sec":"20","scope":"BODY","source_segment_ids":"T3","transcript_text":"c","rule_id":"","rule_priority":"","constraint_type":"NONE","timing_source":"MASTER_TRANSCRIPT"},
        {"slot_id":"P0004","start_time":"1:20","end_time":"1:40","duration_sec":"20","scope":"BODY","source_segment_ids":"T4","transcript_text":"d","rule_id":"","rule_priority":"","constraint_type":"NONE","timing_source":"MASTER_TRANSCRIPT"},
    ]
    with (tmp_path / "08_production_slots.csv").open("w", encoding="utf-8", newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(rows)
    (tmp_path / "production_settings.json").write_text(json.dumps({
        "avatar":40,"ai_images":30,"stock":10,"overlays":20
    }), encoding="utf-8")

    target=allocate_ratio_targets(tmp_path)
    assert target.is_file()
    summary=json.loads((tmp_path/"production_ratio_summary.json").read_text(encoding="utf-8"))
    assert summary["total_duration_seconds"] == 100.0
    assert summary["targets"]["avatar"]["target_seconds"] == 40.0
    assert summary["targets"]["ai_images"]["target_seconds"] == 30.0
    with target.open(encoding="utf-8", newline="") as h:
        allocated=list(csv.DictReader(h))
    assert all(r["ratio_assignment_source"] == "GUI_DURATION_MIX" for r in allocated)
