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


def test_gui_offers_deterministic_timestamp_first_preflight_chain():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(encoding="utf-8")
    production = source.split("def render_production() -> None:", 1)[1].split("def load_production_sheet", 1)[0]
    assert 'st.markdown("### Timestamp-First Preflight")' in production
    workflow = source.split("def render_workflow() -> None:", 1)[1].split("def render_production() -> None:", 1)[0]
    assert 'st.markdown("### Timestamp-First Preflight")' not in workflow
    start = production.index('st.markdown("### Timestamp-First Preflight")')
    end = production.index('cli_template = detect_codex_command()', start)
    block = production[start:end]
    assert "save_rules(project, rule_records)" in block
    assert "build_production_slots(project, config)" in block
    assert "allocate_ratio_targets(project)" in block
    assert "audit_timeline(project)" in block
    assert block.index("build_production_slots(project, config)") < block.index("allocate_ratio_targets(project)") < block.index("audit_timeline(project)")
    assert "run_external_command" not in block
