# Template Contract Deadlock Fix

Applied on top of `Senior_Health_AI_V3_4v_DETERMINISTIC_GATE_VALIDATION_FIX`
(SHA256 `a080d04f…dbf2e4`, verified: integrity PASS, 555 passed / 8 skipped).

## What was wrong

The deterministic validator was correct. The **artifact it validates was not.**

`Templates/Writing/narrative_qa_output_template.md` is the canonical shape of
`14_narrative_qa.md`. It was missing two things the new contract requires:

1. No `## Approved Blueprint Order Audit` heading at all.
2. Its Semantic Progression Gate table was still the old 5-column header — no
   `Material delta vs primary`, no `Approved source trace`. The agent file was
   upgraded to 7 columns in the previous build; this template was never updated.

Empirical result before the fix:

```
Canonical output template -> structurally valid? False
   * missing required section: Approved Blueprint Order Audit
   * Semantic Progression Gate table missing APPROVED SOURCE TRACE column
```

### Why this was a hard deadlock

A Narrative QA run following the canonical template produces a report the validator
downgrades from `PASS` to `FAIL`. `stage_ready("Speech Optimizer")` requires exact
`PASS`. `production_lock()` requires `06a_voice_script.md`, which only the Speech
Optimizer produces. So **no project could reach Production** — correct output, correct
validator, incompatible contract.

The validator's unit tests never caught it because they build synthetic reports that
satisfy the contract by construction. Nothing tested the shipped templates.

## Fixes

1. **`Templates/Writing/narrative_qa_output_template.md`**
   - Semantic Progression Gate table upgraded to the agent's 7-column contract,
     including `Material delta vs primary` and `Approved source trace` with the
     `SOURCE TRACE: NONE` placeholder.
   - Added a full `## Approved Blueprint Order Audit` section with expected order,
     current order, authorization/source and PASS/FAIL columns, plus the
     "correct list order is not proof of blueprint order" reminder.

2. **`v31_core.py :: _markdown_heading_names()`**
   - Heading matching now also registers the bare name when a heading carries a
     trailing annotation. `Agents/Narrative_QA_Agent.md` documents
     `## Semantic Progression Gate (required)`; a report copying that heading
     verbatim would have failed on the annotation alone. Low-risk robustness fix —
     it only ever *adds* an accepted alias, never removes a requirement.

3. **`tests/test_shipped_qa_templates_satisfy_validator.py` (new)**
   - Asserts the shipped output template actually satisfies the validator.
   - Asserts the `(required)` heading variant is accepted.
   - Asserts the agent and output template declare the same semantic columns, so
     the two cannot silently drift apart again.

## Result

`558 passed, 8 skipped, 0 failed`

Changed: `Templates/Writing/narrative_qa_output_template.md`, `v31_core.py`
Added: `tests/test_shipped_qa_templates_satisfy_validator.py`
Removed: none. `production_lock()`, `stage_ready()`, the three Narrative QA locks,
the Speech Optimizer prompt fix and all prior infrastructure fixes are untouched.

## Still worth checking

There is no `06b_voice_checklist.md` template in the repo — the model produces those
five sections from prose instruction only (AGENT.md and, now, the Speech Optimizer
prompt). That is not currently a deadlock because both sources name the sections
exactly, but a shipped checklist template would make it as safe as the Narrative QA
path. Same closed-loop test would then apply.
