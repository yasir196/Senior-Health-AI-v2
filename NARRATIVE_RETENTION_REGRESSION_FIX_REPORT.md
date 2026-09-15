# Narrative Retention Regression Fix Report

Build basis: `Senior_Health_AI_V3_4v_PRE_TITLE_STDIN_FIX(2).zip`

## Issue-by-issue status

| # | Issue | Status | Implementation |
|---:|---|---|---|
| 1 | Semantic repetition detection | FIXED | Narrative QA now audits same ideas across paraphrases and classifies beats NEW / DEEPENS / RECAP / REPEATS. |
| 2 | Whole-script recurrence | FIXED | QA and Retention Analyzer now compare recurring core ideas across the full script and require verbatim anchors plus KEEP/CUT/MERGE decisions. |
| 3 | Information-progression gate | FIXED | Two or more consecutive low-progression beats cannot remain unresolved on PASS. |
| 4 | Multiple recap / multiple ending detection | FIXED | QA explicitly counts redundant recap/ending cycles; Script Agent no longer schedules micro-recaps and blocks stacked recap → final-time → final-picture → conclusion patterns. |
| 5 | Title-payoff timing | FIXED | QA must report where the core title answer begins and becomes substantially complete; materially delayed payoff cannot PASS. Retention Analyzer also checks title-payoff timing. |
| 6 | Safety/qualification consolidation | FIXED | Required medical warnings remain protected, while repeated safety meanings are flagged for safe consolidation. |
| 7 | Narrative QA independence | FIXED | Prior Retention Structure is context only, not proof. QA must adversarially audit the current final script and may require a safe new cut/merge/reorder. |
| 8 | Runtime floor protecting repetition | FIXED | Necessary cuts/merges are designed before runtime convergence. If the corrected script becomes short, only evidence-approved NEW value may be added. Repetition cannot be restored for runtime. |
| 9 | Auto Revision delete/merge patches | FIXED | Auto Revision Engine now supports `Replace With: [DELETE]` for true deletion, in addition to shorter merge/replacement patches. |
| 10 | Invented Estimated AVD prediction | FIXED | Estimated/predicted AVD percentage removed from Narrative QA requirements; QA reports risks, actual AVD remains analytics data. |
| 11 | Repetition as a real gate | FIXED | HIGH repetition, unresolved 3+ semantic recurrence, unresolved redundant endings/recaps, materially delayed payoff, or unresolved 2+ low-progression beats cannot PASS. |
| 12 | Upstream writer guardrail | FIXED | Script Agent and Opus writer now require material progression per beat; curiosity loops, stories, pattern interrupts, and recaps are adaptive rather than fixed quotas. |

## Root-cause correction

The previous Script Agent required curiosity loops every 60–90 seconds, stories every 4–5 minutes, and micro-recaps every 4–5 minutes. Those cadence quotas could manufacture repetition even when the underlying information was already clear. Fixed cadence requirements for loops, stories, and recaps were removed. Recaps are now strategic only.

## Validation

- Python compileall: PASS.
- New semantic-progression regression tests: 4/4 PASS.
- Auto Revision `[DELETE]` behavior: PASS.
- Existing `tests/test_v31_core.py`: 40/42 PASS; the two failures are pre-existing expectations for an older Speech Optimizer gate behavior and are unrelated to this change (current app intentionally allows Speech Optimizer directly from `06_final_script.md`).
- Full pytest collection cannot be used as a clean baseline because two existing tests contain stale absolute `/tmp/...` paths and fail during collection before tests run.
- No Medical Gate logic, Thumbnail learning, Pre-Title checker, analytics DB schema, project paths, or production behavior was changed for this fix.

## Material-Delta Recurrence Tightening — 2026-09-12

Status: PASS

Problem observed in fresh-project testing: Narrative QA could correctly identify a recurring core idea yet still allow repeated applications merely because they appeared in a different section/example/context. This was too permissive for retention.

Implemented:
- Added a mandatory MATERIAL-DELTA TEST to Narrative QA whole-script recurrence auditing.
- For every post-primary occurrence, QA must name the exact new viewer knowledge, decision, mechanism, consequence, evidence, or action that was not already inferable from the primary explanation.
- A different food/example/section, rewording, another hypothetical, or re-attaching the same scope/safety disclaimer does not count as new value by itself.
- For core ideas appearing 3+ times, every post-primary occurrence must expose its material delta. A non-final-recap occurrence with no concrete delta must be CUT/MERGED before PASS.
- One concise final recap remains allowed when it compresses rather than reteaches.
- Applied the same contract upstream to Opus Writer and Retention Structure Analyzer so the system prevents the repetition before downstream QA when possible.
- Mirrored the gate in the runtime Narrative QA command in app.py.

Files changed:
- Agents/Narrative_QA_Agent.md
- Templates/Writing/opus_narrative_qa.md
- Templates/Writing/retention_structure_analyzer.md
- Templates/Writing/opus_writer_prompt.md
- app.py
- tests/test_narrative_material_delta_gate.py

Validation:
- app.py compile: PASS
- Focused regression suite: 20/20 PASS
