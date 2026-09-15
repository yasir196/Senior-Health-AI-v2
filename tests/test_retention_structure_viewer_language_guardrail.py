from pathlib import Path
def test_retention_prompt_forbids_production_vocabulary_in_spoken_patches():
    root = Path(__file__).resolve().parents[1]
    source = (root / "Templates" / "Writing" / "retention_structure_analyzer.md").read_text(encoding="utf-8")
    assert "Inserted / re-hook / bridge text must be viewer-facing narration only." in source
    assert "Never use production vocabulary (retention, hook, re-hook, payoff, CTR, algorithm)" in source
