from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(rel): return (ROOT/rel).read_text(encoding="utf-8")

def test_prompt_layers_keep_density_separate_from_progression():
    for rel in ("Agents/Narrative_QA_Agent.md","Templates/Writing/opus_narrative_qa.md","app.py"):
        s=read(rel).lower()
        assert "density" in s and "progression" in s
        assert "not automatically" in s or "not an automatic" in s or "not a hard failure" in s

def test_runtime_cannot_create_qa_failure_or_revision():
    agent=read("Agents/Narrative_QA_Agent.md")
    app=read("app.py")
    assert "There is no runtime PASS/FAIL status in Narrative QA" in agent
    assert "Runtime must never cause a revision" in app
