from pathlib import Path


def test_learned_channel_rules_are_not_auto_wired_into_writer():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    assert "Analytics/active_channel_script_rules.md" not in app
    assert "ACTIVE CHANNEL SCRIPT RULES" not in app
    assert "auto-injected into the downloaded Opus package" not in app
    assert "Script Outline" in app
    assert "Prepare Opus Package" in app
