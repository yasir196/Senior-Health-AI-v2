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
    # Speech pauses do not create blank visual gaps. The HOOK visual coverage
    # continues from its last spoken segment through the pause to BODY start.
    assert len(hook) == 6
    assert all(float(r["duration_sec"]) <= 5 for r in hook)
    assert hook[-1]["end_time"] == body[0]["start_time"]
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


def test_natural_pause_at_scope_boundary_is_visual_coverage_not_gap(tmp_path: Path) -> None:
    with (tmp_path / "08_master_narration_timeline.csv").open("w", encoding="utf-8", newline="") as h:
        fields=["Segment ID","Transcript Text","Actual Audio Start","Actual Audio End","Duration","Avatar Chunk","Timing Source"]
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
        w.writerows([
            {"Segment ID":"T1","Transcript Text":"hook","Actual Audio Start":"0:24.920","Actual Audio End":"0:31.720","Duration":"6.8","Avatar Chunk":"c1.mp4","Timing Source":"TRANSCRIPT"},
            {"Segment ID":"T2","Transcript Text":"body","Actual Audio Start":"0:32.440","Actual Audio End":"0:38.180","Duration":"5.74","Avatar Chunk":"c1.mp4","Timing Source":"TRANSCRIPT"},
        ])
    save_rules(tmp_path,[
        {"id":"hook","name":"Hook","category":"IMAGE","scope":"HOOK","enabled":True,"priority":200,"hard":True,"min_seconds":4,"max_seconds":5},
        {"id":"body","name":"Body","category":"IMAGE","scope":"BODY","enabled":True,"priority":100,"hard":True,"min_seconds":7,"max_seconds":8},
    ])
    target=build_production_slots(tmp_path,{"production_hook_end_seconds":32})
    with target.open(encoding="utf-8",newline="") as h:
        rows=list(csv.DictReader(h))
    hook=[r for r in rows if r["scope"]=="HOOK"]
    body=[r for r in rows if r["scope"]=="BODY"]
    assert hook[-1]["end_time"] == "0:32.440"
    assert body[0]["start_time"] == "0:32.440"
    assert all(r["transcript_text"] in {"hook", "body"} for r in rows)


def test_split_asr_segment_excerpt_words_are_not_repeated(tmp_path: Path) -> None:
    text = "one two three four five six seven eight nine ten"
    with (tmp_path / "08_master_narration_timeline.csv").open("w", encoding="utf-8", newline="") as h:
        fields=["Segment ID","Transcript Text","Actual Audio Start","Actual Audio End","Duration","Avatar Chunk","Timing Source"]
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
        w.writerow({"Segment ID":"T1","Transcript Text":text,"Actual Audio Start":"0:00","Actual Audio End":"0:10","Duration":"10","Avatar Chunk":"c1.mp4","Timing Source":"TRANSCRIPT"})
    save_rules(tmp_path,[{"id":"hook","name":"Hook","category":"IMAGE","scope":"HOOK","enabled":True,"priority":200,"hard":True,"min_seconds":4,"max_seconds":5}])
    target=build_production_slots(tmp_path,{"production_hook_end_seconds":30})
    with target.open(encoding="utf-8",newline="") as h:
        rows=list(csv.DictReader(h))
    assert len(rows)==2
    emitted=" ".join(r["transcript_text"] for r in rows).split()
    assert emitted == text.split()
    assert len(emitted) == len(set(emitted))


def test_natural_pause_does_not_duplicate_excerpt_text(tmp_path: Path) -> None:
    with (tmp_path / "08_master_narration_timeline.csv").open("w", encoding="utf-8", newline="") as h:
        fields=["Segment ID","Transcript Text","Actual Audio Start","Actual Audio End","Duration","Avatar Chunk","Timing Source"]
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
        w.writerows([
            {"Segment ID":"T1","Transcript Text":"alpha beta gamma delta","Actual Audio Start":"0:00","Actual Audio End":"0:04","Duration":"4"},
            {"Segment ID":"T2","Transcript Text":"epsilon zeta eta theta","Actual Audio Start":"0:04.720","Actual Audio End":"0:08.720","Duration":"4"},
        ])
    save_rules(tmp_path,[{"id":"hook","name":"Hook","category":"IMAGE","scope":"HOOK","enabled":True,"priority":200,"hard":True,"min_seconds":4,"max_seconds":5}])
    target=build_production_slots(tmp_path,{"production_hook_end_seconds":30})
    with target.open(encoding="utf-8",newline="") as h:
        rows=list(csv.DictReader(h))
    emitted=" ".join(r["transcript_text"] for r in rows).split()
    assert emitted == "alpha beta gamma delta epsilon zeta eta theta".split()
