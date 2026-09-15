from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT = (ROOT / "Templates" / "Writing" / "retention_structure_analyzer.md").read_text(encoding="utf-8")

def test_hook_payoff_continuity_rule_is_locked():
    assert "11. HOOK-PAYOFF CONTINUITY:" in PROMPT
    assert "Add an explicit CONTINUITY CHECK inside the Script Chat Revision Prompt" in PROMPT

def test_revision_prompt_requires_continuity_check():
    assert "If any Hook patch promises a specific payoff that is delivered by a later patch or section" in PROMPT
    assert "naming both patch IDs" in PROMPT

def test_existing_viewer_language_guardrail_remains():
    assert "10. Inserted / re-hook / bridge text must be viewer-facing narration only." in PROMPT
    assert "Never use production vocabulary (retention, hook, re-hook, payoff, CTR, algorithm)" in PROMPT
