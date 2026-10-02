from pathlib import Path


def test_production_gui_has_no_estimated_runtime_or_global_image_duration_control():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(encoding="utf-8")
    assert 'number_input("AI image display duration (seconds)"' not in source
    assert 'Estimated runtime:' not in source
    assert 'Estimated AI images:' not in source
    assert "Actual master runtime:" in source
    assert "Visual durations are controlled by the enabled Production Rules" in source


def test_production_gui_reports_deterministic_slot_allocation():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(encoding="utf-8")
    assert 'ratio_slots_path = project / "08_ratio_allocated_slots.csv"' in source
    assert "Deterministically allocated AI-image slots:" in source
    assert '"image_duration_seconds": duration' not in source


def test_actual_runtime_parser_is_imported_from_timeline_builder():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(encoding="utf-8")
    assert "from timeline_builder import TimelineBuildError, build_timeline_manifest, parse_timeline_time" in source
    assert 'parse_timeline_time(row.get("Actual Audio End", "0"))' in source
