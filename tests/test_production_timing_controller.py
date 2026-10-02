import csv
from pathlib import Path

from production_rules import save_rules
from production_timing_controller import build_production_slots


def _master(project: Path) -> None:
    with (project / "08_master_narration_timeline.csv").open("w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=["Segment ID","Transcript Text","Actual Audio Start","Actual Audio End","Duration","Avatar Chunk","Timing Source"])
        w.writeheader()
        w.writerows([
            {"Segment ID":"T0001","Transcript Text":"Hook narration","Actual Audio Start":"0:00.000","Actual Audio End":"0:12.000","Duration":"12","Avatar Chunk":"c1.mp4","Timing Source":"TRANSCRIPT"},
            {"Segment ID":"T0002","Transcript Text":"Body narration","Actual Audio Start":"0:30.000","Actual Audio End":"0:46.000","Duration":"16","Avatar Chunk":"c1.mp4","Timing Source":"TRANSCRIPT"},
        ])


def test_gui_duration_rules_are_applied_to_actual_timestamps(tmp_path: Path) -> None:
    _master(tmp_path)
    save_rules(tmp_path, [
        {"id":"hook","name":"Hook","category":"IMAGE","scope":"HOOK","enabled":True,"priority":200,"hard":True,"min_seconds":4,"max_seconds":5},
        {"id":"body","name":"Body","category":"IMAGE","scope":"BODY","enabled":True,"priority":100,"hard":True,"min_seconds":7,"max_seconds":8},
    ])
    target = build_production_slots(tmp_path, {"production_hook_end_seconds":30})
    with target.open(encoding="utf-8", newline="") as h:
        rows = list(csv.DictReader(h))
    hook = [r for r in rows if r["scope"] == "HOOK"]
    body = [r for r in rows if r["scope"] == "BODY"]
    assert len(hook) == 3
    assert all(float(r["duration_sec"]) <= 5 for r in hook)
    assert len(body) == 2
    assert all(float(r["duration_sec"]) <= 8 for r in body)
    assert all(r["timing_source"] == "MASTER_TRANSCRIPT" for r in rows)


def test_adjacent_short_transcript_segments_are_aggregated_without_asset_forcing(tmp_path: Path) -> None:
    with (tmp_path / "08_master_narration_timeline.csv").open("w", encoding="utf-8", newline="") as h:
        fields=["Segment ID","Transcript Text","Actual Audio Start","Actual Audio End","Duration","Avatar Chunk","Timing Source"]
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
        w.writerows([
            {"Segment ID":"T1","Transcript Text":"a","Actual Audio Start":"0:00","Actual Audio End":"0:02","Duration":"2"},
            {"Segment ID":"T2","Transcript Text":"b","Actual Audio Start":"0:02","Actual Audio End":"0:04.5","Duration":"2.5"},
            {"Segment ID":"T3","Transcript Text":"c","Actual Audio Start":"0:04.5","Actual Audio End":"0:09","Duration":"4.5"},
        ])
    save_rules(tmp_path,[{"id":"hook","name":"Hook image","category":"IMAGE","scope":"HOOK","enabled":True,"priority":200,"hard":True,"min_seconds":4,"max_seconds":5}])
    target=build_production_slots(tmp_path,{"production_hook_end_seconds":30})
    with target.open(encoding="utf-8",newline="") as h: rows=list(csv.DictReader(h))
    assert len(rows)==2
    assert rows[0]["source_segment_ids"]=="T1|T2"
    assert all(4 <= float(r["duration_sec"]) <= 5 for r in rows)
    assert "recommended_asset_type" not in rows[0]
