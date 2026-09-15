"""The deterministic gate validator must accept the templates we actually ship.

The validator's own unit tests use hand-written synthetic reports. That leaves a
blind spot: if a shipped template drifts from the contract, every real Narrative QA
run is downgraded PASS -> FAIL and the pipeline deadlocks (Speech Optimizer requires
exact PASS, and production_lock requires the voice script only that stage produces).
These tests close the loop between the contract and the artifacts that satisfy it.
"""

from pathlib import Path

from v31_core import validate_qa_report_sections

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_narrative_output_template_satisfies_the_validator() -> None:
    template = (ROOT / "Templates" / "Writing" / "narrative_qa_output_template.md").read_text(encoding="utf-8")
    ok, missing = validate_qa_report_sections("Narrative QA", "Status: PASS\n" + template)
    assert ok, f"shipped narrative QA output template violates the gate contract: {missing}"


def test_agent_semantic_gate_heading_variant_is_accepted() -> None:
    """The agent documents '## Semantic Progression Gate (required)'."""
    report = (
        "Status: PASS\n\n"
        "## Semantic Progression Gate (required)\n\n"
        "| Beat | Classification | Approved source trace | Action |\n"
        "|---|---|---|---|\n"
        "| Hook | NEW | 05_script_outline.md | KEEP |\n\n"
        "## Approved Blueprint Order Audit\n\n"
        "## Active Channel Rule Compliance\n"
    )
    ok, missing = validate_qa_report_sections("Narrative QA", report)
    assert ok, missing


def test_agent_and_output_template_declare_the_same_semantic_columns() -> None:
    agent = (ROOT / "Agents" / "Narrative_QA_Agent.md").read_text(encoding="utf-8")
    template = (ROOT / "Templates" / "Writing" / "narrative_qa_output_template.md").read_text(encoding="utf-8")
    for column in ("Material delta vs primary", "Approved source trace"):
        assert column in agent, f"agent lost the {column!r} column"
        assert column in template, f"output template lost the {column!r} column"
