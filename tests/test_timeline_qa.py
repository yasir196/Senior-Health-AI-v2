import csv
import json
from pathlib import Path

from production_rules import save_rules
from timeline_qa import audit_timeline


FIELDS=["slot_id","start_time","end_time","duration_sec","scope","target_lane","recommended_asset_type"]


def _write(project: Path, rows: list[dict[str,str]]) -> None:
    with (project/"08_ratio_allocated_slots.csv").open("w",encoding="utf-8",newline="") as h:
        w=csv.DictWriter(h,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    save_rules(project,[{"id":"body","name":"Body","category":"IMAGE","scope":"BODY","enabled":True,"priority":100,"hard":True,"min_seconds":4,"max_seconds":8}])


def test_timeline_qa_passes_contiguous_valid_slots(tmp_path: Path) -> None:
    _write(tmp_path,[
        {"slot_id":"P1","start_time":"0:00.000","end_time":"0:05.000","duration_sec":"5.000","scope":"BODY","target_lane":"avatar","recommended_asset_type":"AVATAR"},
        {"slot_id":"P2","start_time":"0:05.000","end_time":"0:10.000","duration_sec":"5.000","scope":"BODY","target_lane":"ai_images","recommended_asset_type":"AI_IMAGE"},
    ])
    report=audit_timeline(tmp_path)
    assert report["status"]=="PASS"
    assert report["hard_issue_count"]==0


def test_timeline_qa_detects_gap_overlap_and_rule_violation(tmp_path: Path) -> None:
    _write(tmp_path,[
        {"slot_id":"P1","start_time":"0:00.000","end_time":"0:09.000","duration_sec":"9.000","scope":"BODY","target_lane":"avatar","recommended_asset_type":"AVATAR"},
        {"slot_id":"P2","start_time":"0:10.000","end_time":"0:13.000","duration_sec":"3.000","scope":"BODY","target_lane":"ai_images","recommended_asset_type":"AI_IMAGE"},
        {"slot_id":"P3","start_time":"0:12.000","end_time":"0:17.000","duration_sec":"5.000","scope":"BODY","target_lane":"stock","recommended_asset_type":"STOCK_VIDEO"},
    ])
    report=audit_timeline(tmp_path)
    kinds={issue["type"] for issue in report["issues"]}
    assert report["status"]=="FAIL"
    assert {"GAP","OVERLAP","RULE_MAX","RULE_MIN"}.issubset(kinds)
    saved=json.loads((tmp_path/"timeline_qa_report.json").read_text(encoding="utf-8"))
    assert saved["status"]=="FAIL"
