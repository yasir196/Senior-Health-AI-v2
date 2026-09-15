from pathlib import Path
from v31_core import validate_qa_report_sections

ROOT = Path(__file__).resolve().parents[1]

def test_agent_runtime_is_advisory_only():
    text=(ROOT/'Agents'/'Narrative_QA_Agent.md').read_text(encoding='utf-8')
    assert 'RUNTIME ADVISORY-ONLY LOCK' in text
    assert 'There is no runtime PASS/FAIL status in Narrative QA' in text
    assert 'SOURCE_POOL_EFFECTIVELY_EXHAUSTED' not in text

def test_template_runtime_is_non_blocking():
    text=(ROOT/'Templates'/'Writing'/'opus_narrative_qa.md').read_text(encoding='utf-8')
    assert 'Runtime Advisory — Non-Blocking' in text
    assert 'QA effect: NONE' in text
    assert 'Runtime Shortfall Cause' not in text
    assert 'Remaining Approved Material Audit' not in text
    assert 'Convergence Check' not in text

def test_app_command_runtime_is_advisory():
    text=(ROOT/'app.py').read_text(encoding='utf-8')
    start=text.index('"Narrative QA": f"For {ref}, run Narrative_QA_Agent')
    end=text.index('"Medical Gate 2":',start)
    cmd=text[start:end]
    assert 'RUNTIME ADVISORY-ONLY LOCK' in cmd
    assert 'based ONLY on narrative-quality, structure, repetition/progression, payoff, and safety-placement gates' in cmd
    assert 'Runtime must never cause a revision' in cmd

def test_deterministic_validator_ignores_runtime_shortfall_claims():
    report="""
Status: PASS
## Semantic Progression Gate
| Beat | Approved source trace |
|---|---|
| x | Research R1 |
## Approved Blueprint Order Audit
PASS
## Active Channel Rule Compliance
PASS
## Runtime Analysis
Runtime Shortfall Cause: SOURCE_POOL_EFFECTIVELY_EXHAUSTED
"""
    ok, issues=validate_qa_report_sections('Narrative QA',report)
    assert ok, issues
