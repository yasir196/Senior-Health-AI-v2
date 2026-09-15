from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def test_agent_makes_missing_trace_nonblocking():
    s = read('Agents/Narrative_QA_Agent.md')
    assert 'EVIDENCE REVIEW HANDOFF — NON-BLOCKING IN NARRATIVE QA' in s
    assert 'EVIDENCE REVIEW FLAG — SOURCE TRACE: NONE' in s
    assert 'Do NOT CUT, MERGE, rewrite, lower the Narrative QA verdict, or create a Revision Patch solely because source trace is missing.' in s
    assert 'Medical Gate 2 / Fact Check owns the accept/reject decision' in s

def test_template_handoff_is_nonblocking():
    s = read('Templates/Writing/opus_narrative_qa.md')
    assert '## Evidence Review Handoff — Non-Blocking in Narrative QA' in s
    assert 'KEEP — MG2 REVIEW' in s
    assert 'Missing provenance alone MUST NOT cause CUT/MERGE, a Revision Patch, PASS WITH REVISIONS, or FAIL.' in s
    assert 'Evidence Review Flags are non-blocking' in s

def test_runtime_stays_advisory():
    s = read('Agents/Narrative_QA_Agent.md')
    assert 'Runtime is reported for production planning only and never determines the Narrative QA verdict or revisions.' in s
    assert 'QA effect: NONE — runtime is advisory and cannot change the Narrative QA verdict' in s

def test_runtime_command_handoff_contract():
    s = read('app.py')
    assert 'EVIDENCE REVIEW HANDOFF — NON-BLOCKING' in s
    assert 'Evidence Review Flags never block Narrative QA and proceed to Medical Gate 2 / Fact Check.' in s
    assert 'Missing source provenance alone can never be a patch reason.' in s
