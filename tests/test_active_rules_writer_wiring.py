from pathlib import Path

def test_writer_and_stage_wiring_present():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    assert "Analytics/active_channel_script_rules.md" in app
    assert "ACTIVE CHANNEL SCRIPT RULES" in app
    assert "render_active_channel_rules_markdown(ANALYTICS_DB_PATH)" in app
    assert "Script Outline" in app
    assert "Prepare Opus Package" in app
    assert "auto-injected into the downloaded Opus package" in app
