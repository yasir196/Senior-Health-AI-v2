from pathlib import Path


def test_prepare_opus_package_requires_lock_preservation():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    assert "HARD PRESERVATION RULE" in app
    assert "copy the complete `## Semantic Progression Lock`, `## Retention-First Drafting Lock`, and `## Execution / No-Negotiation Lock` sections" in app
    assert "without summarizing, weakening, paraphrasing, or omitting their rules" in app
    assert "if no concrete material delta exists, omit or merge the recurrence" in app
    assert "allow at most one concise final recap that compresses rather than reteaches" in app
