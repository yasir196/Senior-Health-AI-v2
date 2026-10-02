import csv
import json
from pathlib import Path

from timeline_builder import build_timeline_manifest


def test_locked_ratio_slots_are_default_capcut_timebase(tmp_path):
    project = tmp_path / "Project"
    project.mkdir()
    fields = ["slot_id","start_time","end_time","duration_sec","scope","source_segment_ids","transcript_text","rule_id","rule_priority","constraint_type","timing_source","target_lane","recommended_asset_type"]
    with (project / "08_ratio_allocated_slots.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        writer.writerow({"slot_id":"P0001","start_time":"0:00.000","end_time":"0:02.500","duration_sec":"2.500","transcript_text":"Locked narration","timing_source":"MASTER_TRANSCRIPT","target_lane":"avatar","recommended_asset_type":"AVATAR"})
    (project / "avatar_timing_manifest.json").write_text(json.dumps({"timeline_status":"PASS","total_avatar_duration":2.5,"chunks":[{"chunk_filename":"c1.mp4","global_audio_start":0.0,"global_audio_end":2.5,"duration":2.5}]}), encoding="utf-8")
    result = build_timeline_manifest(project)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["timebase"]["source"] == "08_ratio_allocated_slots.csv"
    assert manifest["scenes"][0]["scene_id"] == "P0001"
    assert manifest["scenes"][0]["timing"]["start_seconds"] == 0.0
    assert manifest["scenes"][0]["timing"]["end_seconds"] == 2.5


def test_gui_capcut_handoff_requires_locked_slots_and_timeline_qa():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    assert 'locked_timeline_path = project / "08_ratio_allocated_slots.csv"' in app
    assert 'capcut_qa.get("status") == "PASS"' in app
    assert "build_timeline_manifest(project, locked_timeline_path)" in app
    assert "legacy 08_actual_timeline.csv is not the CapCut production authority" in app
