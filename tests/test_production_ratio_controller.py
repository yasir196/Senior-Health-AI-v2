import csv
import json
from pathlib import Path

from production_ratio_controller import allocate_ratio_targets, validate_ratio_result


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


def test_ratio_tolerance_passes_within_configured_points() -> None:
    summary = {"targets": {"avatar": {"target_percent": 40, "actual_percent": 43.5}}}
    assert validate_ratio_result(summary, tolerance_points=5, strict=False) == []


def test_ratio_tolerance_fails_outside_configured_points() -> None:
    summary = {"targets": {"avatar": {"target_percent": 40, "actual_percent": 46}}}
    issues = validate_ratio_result(summary, tolerance_points=5, strict=False)
    assert issues and "exceeds" in issues[0]


def test_strict_ratio_mode_uses_near_exact_threshold() -> None:
    summary = {"targets": {"avatar": {"target_percent": 40, "actual_percent": 40.02}}}
    assert validate_ratio_result(summary, tolerance_points=5, strict=True)


def test_ratio_is_distributed_from_hook_instead_of_front_loading_ai_images(tmp_path: Path) -> None:
    fields=["slot_id","start_time","end_time","duration_sec","scope","source_segment_ids","transcript_text","rule_id","rule_priority","constraint_type","timing_source"]
    rows=[]
    for i in range(10):
        rows.append({"slot_id":f"P{i+1:04d}","start_time":str(i*5),"end_time":str((i+1)*5),"duration_sec":"5","scope":"HOOK" if i<6 else "BODY","source_segment_ids":f"T{i+1}","transcript_text":"x","rule_id":"","rule_priority":"","constraint_type":"NONE","timing_source":"MASTER_TRANSCRIPT"})
    with (tmp_path/"08_production_slots.csv").open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(rows)
    (tmp_path/"production_settings.json").write_text(json.dumps({"avatar":40,"ai_images":60,"stock":0,"overlays":0}),encoding="utf-8")
    target=allocate_ratio_targets(tmp_path)
    with target.open(encoding="utf-8",newline="") as h: allocated=list(csv.DictReader(h))
    hook=[r for r in allocated if r["scope"]=="HOOK"]
    assert {r["recommended_asset_type"] for r in hook}=={"AVATAR","AI_IMAGE"}


def test_invalid_image_duration_is_assigned_to_avatar_not_ai_image(tmp_path: Path) -> None:
    from production_rules import save_rules
    fields=["slot_id","start_time","end_time","duration_sec","scope","source_segment_ids","transcript_text","rule_id","rule_priority","constraint_type","timing_source"]
    rows=[
        {"slot_id":"P0001","start_time":"0","end_time":"3","duration_sec":"3","scope":"BODY","source_segment_ids":"T1","transcript_text":"x","rule_id":"body","rule_priority":"100","constraint_type":"HARD","timing_source":"MASTER_TRANSCRIPT"},
        {"slot_id":"P0002","start_time":"3","end_time":"10","duration_sec":"7","scope":"BODY","source_segment_ids":"T2","transcript_text":"y","rule_id":"body","rule_priority":"100","constraint_type":"HARD","timing_source":"MASTER_TRANSCRIPT"},
    ]
    with (tmp_path/"08_production_slots.csv").open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(rows)
    save_rules(tmp_path,[{"id":"body","name":"Body image","category":"IMAGE","scope":"BODY","enabled":True,"priority":100,"hard":True,"min_seconds":7,"max_seconds":8}])
    (tmp_path/"production_settings.json").write_text(json.dumps({"avatar":40,"ai_images":60,"stock":0,"overlays":0}),encoding="utf-8")
    target=allocate_ratio_targets(tmp_path)
    with target.open(encoding="utf-8",newline="") as h: allocated=list(csv.DictReader(h))
    assert allocated[0]["recommended_asset_type"]=="AVATAR"
    assert allocated[1]["recommended_asset_type"]=="AI_IMAGE"
