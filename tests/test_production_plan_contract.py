from pathlib import Path

import pytest

from production_plan_contract import validate_ai_timing_lock


def _slot_file(project: Path) -> None:
    (project / "08_ratio_allocated_slots.csv").write_text(
        "slot_id,start_time,end_time,duration_sec,transcript_text\n"
        "P0001,0:00.000,0:05.000,5.000,Exact narration\n",
        encoding="utf-8",
    )


def test_visual_planner_cannot_change_locked_timing(tmp_path: Path) -> None:
    _slot_file(tmp_path)
    rows = [{"start_time":"0:00.000","end_time":"0:06.000","duration_sec":"6.000","script_excerpt":"Exact narration"}]
    issues = validate_ai_timing_lock(tmp_path, rows)
    assert any("end_time is locked" in issue for issue in issues)
    assert any("duration_sec is locked" in issue for issue in issues)


def test_visual_planner_cannot_change_slot_count(tmp_path: Path) -> None:
    _slot_file(tmp_path)
    assert validate_ai_timing_lock(tmp_path, []) 


def test_exact_locked_row_passes(tmp_path: Path) -> None:
    _slot_file(tmp_path)
    rows = [{"start_time":"0:00.000","end_time":"0:05.000","duration_sec":"5.000","script_excerpt":"Exact narration"}]
    assert validate_ai_timing_lock(tmp_path, rows) == []


def test_app_enforces_timestamp_lock_after_ai_generation():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    assert "from production_plan_contract import validate_ai_timing_lock" in app
    assert "timing_lock_issues = validate_ai_timing_lock(project, final_production_rows)" in app
    assert "TIMING_LOCK_QA_FAILED" in app
    assert "AI changed Python-owned timestamp slots or locked transcript text" in app
