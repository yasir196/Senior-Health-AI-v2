# Deterministic Gate Validation Fix

Base: `Senior_Health_AI_V3_4v_NARRATIVE_SOURCE_ORDER_RUNTIME_FIX.zip`

## Scope

This patch closes two remaining instruction-only loopholes without changing Narrative QA scoring, Material-Delta behavior, Production Lock semantics, Medical Gate 2 logic, or the Claude infrastructure fixes already present.

### 1. Speech Optimizer prompt contract

`app.py` no longer tells the Speech Optimizer to ignore Narrative QA / Medical Gate 2. The generated command now requires both upstream gates to report exactly `PASS` and explicitly rejects conditional verdicts.

### 2. Deterministic Narrative QA report validation

`v31_core.py` adds `validate_qa_report_sections()` and hooks it into `get_gate_status()`.

A Narrative QA report claiming `Status: PASS` is downgraded to `FAIL` unless it contains:

- `## Semantic Progression Gate`
- an `APPROVED SOURCE TRACE` column in that gate's table
- `## Approved Blueprint Order Audit`
- `## Active Channel Rule Compliance`

The failure reason names the missing section/column.

### 3. Deterministic Speech Optimizer checklist validation

`06b_voice_checklist.md` is validated for:

- `Speech QA`
- `Paragraph Statistics`
- `Pronunciation Review`
- `Chapter Plan`
- `Upload Checklist`

Because the existing Voice template does not require a free-form `Status:` line, a complete checklist is treated as `PASS`; an incomplete checklist is `FAIL` with the missing section named.

`production_lock()` remains unchanged and still gates only on the canonical voice script, preserving the established Claude fix and its tests.

## Tests

Added `tests/test_deterministic_qa_report_contracts.py` and updated the older gate fixtures in `tests/test_v31_core.py` so their synthetic `PASS` Narrative QA reports satisfy the newer deterministic contract.

Full suite result:

`555 passed, 8 skipped, 0 failed`
