# Narrative Evidence Handoff Fix

## Goal
Stop Narrative QA from acting as a duplicate Fact Check / Medical Gate while preserving evidence visibility and medical review downstream.

## Behavior
- Runtime remains advisory-only and cannot affect Narrative QA verdicts or patches.
- Narrative QA still classifies factual additions for auditability.
- Missing explicit source provenance is now `EVIDENCE REVIEW FLAG — SOURCE TRACE: NONE` and `KEEP — MG2 REVIEW`.
- Missing provenance alone cannot cause CUT/MERGE, Revision Patch, PASS WITH REVISIONS, or FAIL.
- Medical Gate 2 / Fact Check owns evidence accept/reject decisions.
- Narrative QA may revise a flagged sentence only when an independent narrative defect exists (repetition, delayed payoff, hierarchy, safety placement, blueprint/order, etc.).
- Narrative QA must not invent new factual material while patching.
- Material-Delta repetition, information progression, blueprint order, payoff, active-rule verification, and safety-placement gates remain active.

## Files Changed
- Agents/Narrative_QA_Agent.md
- Templates/Writing/opus_narrative_qa.md
- app.py
- tests/test_narrative_source_materiality_gate.py (updated contract)
- tests/test_narrative_qa_runtime_convergence.py (updated contract wording)
- tests/test_narrative_runtime_advisory_only.py (updated contract wording)
- tests/test_narrative_source_order_runtime_locks.py (updated contract)
- tests/test_narrative_evidence_handoff_nonblocking.py (new)

## Validation
- Python compile: PASS (`app.py`, `v31_core.py`)
- Focused Narrative QA tests: 9 passed
- Full suite with external Streamlit import stub: 608 passed, 8 skipped, 0 failed
- The external Streamlit stub is not included in this project/build.
