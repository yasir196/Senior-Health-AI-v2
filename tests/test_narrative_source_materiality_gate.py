from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def test_agent_source_classification_is_preserved_but_nonblocking():
    s = text('Agents/Narrative_QA_Agent.md')
    assert 'MATERIAL FACTUAL CLAIM' in s
    assert 'SOURCE-FAITHFUL EXPLANATION / PARAPHRASE' in s
    assert 'NARRATIVE CONNECTIVE' in s
    assert 'EXPLANATORY PARAPHRASE — TRACE:' in s
    assert 'NO SOURCE REQUIRED' in s
    assert 'EVIDENCE REVIEW FLAG — SOURCE TRACE: NONE' in s
    assert 'NON-BLOCKING' in s

def test_opus_hands_missing_trace_to_mg2():
    s = text('Templates/Writing/opus_narrative_qa.md')
    assert 'Evidence Review Handoff — Non-Blocking in Narrative QA' in s
    assert 'Type A material factual claim' in s
    assert 'Type B source-faithful explanation/paraphrase' in s
    assert 'Type C narrative connective' in s
    assert 'KEEP — MG2 REVIEW' in s
    assert 'Medical Gate 2 / Fact Check owns the evidence decision' in s

def test_runtime_command_mirrors_nonblocking_handoff():
    s = text('app.py')
    assert 'EVIDENCE REVIEW HANDOFF — NON-BLOCKING' in s
    assert 'EXPLANATORY PARAPHRASE — TRACE:' in s
    assert 'NARRATIVE CONNECTIVE — NO SOURCE REQUIRED' in s
    assert 'EVIDENCE REVIEW FLAG — SOURCE TRACE: NONE' in s
    assert 'Evidence Review Flags never block Narrative QA' in s
