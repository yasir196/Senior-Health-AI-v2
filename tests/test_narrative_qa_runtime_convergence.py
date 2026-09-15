from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(rel): return (ROOT/rel).read_text(encoding="utf-8")

def test_agent_runtime_is_advisory_only():
    s=read("Agents/Narrative_QA_Agent.md")
    assert "RUNTIME ADVISORY-ONLY LOCK" in s
    assert "There is no runtime PASS/FAIL status in Narrative QA" in s
    assert "Never use `PASS WITH REVISIONS` solely because of runtime" in s

def test_template_uses_same_advisory_policy():
    s=read("Templates/Writing/opus_narrative_qa.md")
    assert "Runtime Advisory — Non-Blocking" in s
    assert "QA effect: NONE" in s
    assert "Do not create any Revision Patch whose reason is runtime or word count" in s

def test_direct_run_prompt_blocks_runtime_gating():
    s=read("app.py")
    assert "RUNTIME ADVISORY-ONLY LOCK" in s
    assert "based ONLY on narrative-quality, structure, repetition/progression, payoff, and safety-placement gates" in s
    assert "Runtime must never cause a revision" in s
