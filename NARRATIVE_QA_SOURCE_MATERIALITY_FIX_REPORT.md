# Narrative QA Source Materiality Fix

## Goal
Prevent Narrative QA from cutting ordinary source-faithful explanation merely because the exact explanatory sentence is not present verbatim in research, while preserving strict blocking for genuinely new unsupported factual/medical claims.

## Root cause
The prior Source-Bound Delta Gate treated every factual NEW/DEEPENS proposition as requiring its own direct sentence-level approved trace. That made normal explanatory prose vulnerable to `SOURCE TRACE: NONE`, producing excessive CUT/MERGE patches even when the explanation simply clarified an already approved claim.

## Fix
The Source-Bound Delta Gate is now materiality-aware:

- **Type A — MATERIAL FACTUAL CLAIM**: new/changed mechanism, causality, health effect, disease/treatment implication, risk, numeric detail, comparison, prevalence/commonness, product/category generalization, label/regulatory rule, research-method interpretation, or another proposition that materially changes viewer understanding. Requires explicit approved source trace. `SOURCE TRACE: NONE` remains blocking.
- **Type B — SOURCE-FAITHFUL EXPLANATION / PARAPHRASE**: plain-language explanation faithfully entailed by an approved parent claim and adding no new mechanism/effect/cause/quantity/comparison/risk/scope/conclusion. Allowed with `EXPLANATORY PARAPHRASE — TRACE: <source>`; no separate sentence-level source is required.
- **Type C — NARRATIVE CONNECTIVE**: non-factual transition, analogy framing, orientation, or rhetoric. Allowed with `NARRATIVE CONNECTIVE — NO SOURCE REQUIRED`.

When uncertain whether wording materially expands an approved claim, Narrative QA must treat it as Type A and require a direct source trace.

## Preserved safeguards
- Unsupported new medical/factual claims remain blocking.
- Medical/evidence safety gates remain unchanged.
- Material-Delta repetition gate remains unchanged.
- Approved Blueprint Order gate remains unchanged.
- Runtime remains advisory-only and cannot affect Narrative QA verdict.
- Writer behavior was not changed.

## Files changed
- `Agents/Narrative_QA_Agent.md`
- `Templates/Writing/opus_narrative_qa.md`
- `app.py` (Narrative QA runtime command only)
- `tests/test_narrative_source_order_runtime_locks.py` (contract assertion update)
- `tests/test_narrative_source_materiality_gate.py` (new regression tests)

## Validation
- Python compile: PASS (`app.py`, `v31_core.py`)
- Focused Narrative QA contract tests: **22 passed**
- Full runnable suite excluding the pre-title module that cannot import in this sandbox because `streamlit` is not installed: **579 passed, 8 skipped**
- The excluded pre-title module was not modified by this fix.
