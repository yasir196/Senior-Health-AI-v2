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


def test_rule_controller_and_preflight_share_production_scope():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app.py").read_text(encoding="utf-8")
    production = source.split("def render_production() -> None:", 1)[1].split("def load_production_sheet", 1)[0]
    workflow = source.split("def render_workflow() -> None:", 1)[1].split("def render_production() -> None:", 1)[0]
    assert 'st.markdown("### Production Rule Controller")' in production
    assert "rule_records = edited_rules.fillna" in production
    assert "rule_issues = validate_rules(rule_records)" in production
    assert 'st.markdown("### Timestamp-First Preflight")' in production
    assert production.index("rule_issues = validate_rules(rule_records)") < production.index('st.markdown("### Timestamp-First Preflight")')
    assert 'st.markdown("### Production Rule Controller")' not in workflow


def test_avatar_panel_does_not_apply_legacy_voice_excerpt_gate_after_master_clock_exists() -> None:
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    block = source.split("def render_avatar_timing_sync",1)[1].split("def load_production_sheet",1)[0]
    assert 'timestamp_first_active = master_clock_path.is_file()' in block
    assert 'if scenes and not timestamp_first_active:' in block
    assert 'exact 06a script-excerpt matching is not used after transcription' in block


def test_avatar_panel_shows_master_clock_metrics_in_timestamp_first_mode() -> None:
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    block = source.split("def render_avatar_timing_sync",1)[1].split("def load_production_sheet",1)[0]
    assert 'e2.metric("Master Clock Status", master_clock_status)' in block
    assert 'e3.metric("Master Runtime"' in block
    assert 'e4.metric("Master Segments", master_clock_segments)' in block
    assert 'e2.metric("Legacy Alignment Score"' in block
    assert 'e3.metric("Legacy Timeline Status"' in block


def test_avatar_master_clock_metrics_use_available_csv_reader() -> None:
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    block = source.split("def render_avatar_timing_sync",1)[1].split("def load_production_sheet",1)[0]
    assert 'master_rows = list(csv.DictReader(handle))' in block
    assert 'read_csv_rows(master_clock_path)' not in block
