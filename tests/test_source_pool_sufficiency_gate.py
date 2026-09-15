from pathlib import Path
from v31_core import validate_qa_report_sections
ROOT=Path(__file__).resolve().parents[1]

def test_narrative_validator_does_not_gate_on_runtime_source_pool():
    report="""Status: PASS
## Semantic Progression Gate
| Beat | Approved source trace |
|---|---|
| x | R1 |
## Approved Blueprint Order Audit
PASS
## Active Channel Rule Compliance
PASS
## Runtime Analysis
Runtime Shortfall Cause: UNUSED_APPROVED_MATERIAL
"""
    ok, issues=validate_qa_report_sections("Narrative QA",report)
    assert ok, issues

def test_prompt_surfaces_retire_source_pool_runtime_routing():
    agent=(ROOT/"Agents/Narrative_QA_Agent.md").read_text(encoding="utf-8")
    opus=(ROOT/"Templates/Writing/opus_narrative_qa.md").read_text(encoding="utf-8")
    template=(ROOT/"Templates/Writing/narrative_qa_output_template.md").read_text(encoding="utf-8")
    assert "Do not consult or update `runtime_redevelopment_ledger.json`" in agent
    assert "source-pool sufficiency" in opus.lower()
    assert "Runtime Shortfall Cause:" not in template
