from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_agent_has_evidence_review_handoff():
    s = text("Agents/Narrative_QA_Agent.md")
    assert "EVIDENCE REVIEW HANDOFF" in s
    assert "SOURCE TRACE: NONE" in s
    assert "NON-BLOCKING" in s
    assert "EXPLANATORY PARAPHRASE" in s
    assert "Medical Gate 2 / Fact Check owns the accept/reject decision" in s

def test_agent_has_blueprint_order_gate():
    s = text("Agents/Narrative_QA_Agent.md")
    assert "BLUEPRINT ORDER GATE" in s
    assert "Approved Blueprint Order Audit" in s
    assert "misplaced Introduction" in s
    assert "unresolved unapproved major-section reorder cannot PASS" in s

def test_agent_runtime_is_advisory_not_a_gate():
    s = text("Agents/Narrative_QA_Agent.md")
    assert "RUNTIME ADVISORY-ONLY LOCK" in s
    assert "There is no runtime PASS/FAIL status in Narrative QA" in s
    assert "runtime_redevelopment_ledger.json" in s
    assert "Do not consult or update" in s

def test_opus_qa_mirrors_three_locks():
    s = text("Templates/Writing/opus_narrative_qa.md")
    assert "## Evidence Review Handoff — Non-Blocking in Narrative QA" in s
    assert "## Approved Blueprint Order Audit" in s
    assert "## Runtime Advisory — Non-Blocking" in s
    assert "SOURCE TRACE: NONE" in s

def test_direct_runtime_prompt_mirrors_three_locks():
    s = text("app.py")
    assert "Approved source trace" in s
    assert "Approved Blueprint Order Audit" in s
    assert "RUNTIME ADVISORY-ONLY LOCK" in s
    assert "retention_structure_analysis.md when present" in s
