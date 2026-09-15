# Topic Validation — Title-Led Research Fix

## Scope
Narrow Stage 1 fix only. Pre-Title remains outside the pipeline and no pre-title JSON handoff was added.

## Problem
Stage 1 treated `01a_anchor_claim_map.json` as an exhaustive/authoritative medical hypothesis. When its parser left fields blank (for example an intentionally withheld curiosity payoff), Stage 1 could FAIL before doing topic research.

## Fix
- The immutable `project.json.anchor_title` is now the sole wording authority for Stage 1.
- `01a_anchor_claim_map.json` is explicitly a parser-produced packaging scaffold, not an evidence verdict.
- Missing/blank claim-map fields or `UNVERIFIED_HYPOTHESIS` cannot by themselves cause FAIL.
- Stage 1 must independently research the exact title promise to Topic-Validation depth before deciding.
- Material propositions are tested separately, including mechanism/outcome, population relevance, prevalence/quantifier, timing/dose, and safety boundaries when applicable.
- Research must include supporting plus narrowing/contrary evidence and seek evidence saturation (normally ~4–8 useful verified sources when available, not a hard quota).
- Curiosity titles may have an unstated payoff; Stage 1 may establish an evidence-supported working interpretation without changing the title or claim-map JSON.
- Quantifier/prevalence claims are checked independently from mechanism evidence.
- FAIL is reserved for genuine evidence/demand/safety conflicts after research, not parser incompleteness.

## Files changed
- `Agents/Outlier_Agent.md`
- `app.py`

## Explicitly unchanged
- Pre-Title flow/integration
- `v31_core.py` claim-map generation
- `project.json` / title immutability behavior
- Research Agent, Medical Gates, downstream pipeline behavior
