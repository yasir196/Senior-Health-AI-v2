# Source Pool Sufficiency Gate

Applied on top of `Senior_Health_AI_V3_4v_CANONICAL_RUNTIME_LOCK`.
Result: **583 passed, 8 skipped, 0 failed** (was 569).

---

## The remaining bug, confirmed from the shipped report

The diagnosis was right, and the report proves it against itself:

- Line 113 — cause `UNUSED_APPROVED_MATERIAL`, and the named remainder is *entirely*
  study-population detail: 3,656 adults / ages 63–83; 34 RCTs / 2,830 adults;
  12 RCTs / 491 adults.
- Line 93 — ACTIVE **Rule 2: Dense information delivery = FAIL**, revision required YES.

So the same report fails the script for density and then instructs the Writer to add more
study counts. It also writes *"Writer/Outline must decide whether any can add a distinct
viewer insight"* — QA deferring the sufficiency judgement that is its own job. Three
population-count fragments cannot yield 441 distinct words; the classifier only ever
checked that the pool was non-empty.

## Fixes

**1. Three-state classification replaces the binary** (`v31_core.py`, agent, Opus template,
`app.py` prompt, output template)

| Cause | Meaning | Route |
|---|---|---|
| `UNUSED_APPROVED_MATERIAL_SUFFICIENT` | audited yield ≥ shortfall, distinct value, no density cost | Writer/Outline |
| `SOURCE_POOL_EFFECTIVELY_EXHAUSTED` | items remain but cannot close the shortfall | escalate |
| `SOURCE_POOL_EXHAUSTED` | nothing approved remains | escalate |

The bare `UNUSED_APPROVED_MATERIAL` is retired and rejected.

**2. Sufficiency must be arithmetic, not assertion**

`SUFFICIENT` now requires a `Remaining Approved Material Audit` — every remaining item with
its source, the distinct insight it would add, an `Estimated clean words` figure, and an
"adds density only?" flag.

`parse_runtime_shortfall()` + `validate_qa_report_sections()` then **check the sum**. If the
report claims `SUFFICIENT` but its own itemized yield is below the stated shortfall, the gate
fails with the exact numbers:

```
UNUSED_APPROVED_MATERIAL_SUFFICIENT is not supported by its own audit:
itemized yield is 135 words against a 441-word shortfall.
Classify as SOURCE_POOL_EFFECTIVELY_EXHAUSTED and escalate instead of routing to Writer.
```

This is the part that cannot be talked around: the model must put a number next to each
remaining source, and three population-count fragments will not add up to 441.

**3. Density interlock (agent rule 29)** — expansion may not be requested in any cycle where
an ACTIVE rule is FAIL. That cycle is cuts-and-fixes only; runtime sufficiency is judged next
run against the corrected script. This directly forbids the contradiction in the shipped
report.

**4. Redevelopment budget (agent rule 30)** — a deterministic termination backstop.
`runtime_redevelopment_ledger.json` records each runtime-driven routing, keyed by script
hash so Streamlit reruns cannot double-count. Once
`max_runtime_redevelopment_cycles` (new config key, default **2**) is spent, escalation is
forced regardless of how the model classifies. Whatever the prompt layer does, the loop
now terminates.

**5. Bug found while building this** — the cause parser stripped `_` as Markdown emphasis,
which mangled `UNUSED_APPROVED_MATERIAL` into `UNUSEDAPPROVEDMATERIAL`. Fixed and pinned by
a test; underscores are part of the tokens, not formatting.

**6. Tests** — `tests/test_source_pool_sufficiency_gate.py` (14 tests) covering each state,
the arithmetic rejection, audit absence, escalation paths needing no audit, clean PASS
reports being unaffected, ledger idempotency and corruption tolerance, and prompt-surface
coverage.

Verified against your actual report:

```
Real report -> status: FAIL
reason: Runtime Shortfall Cause is the retired value UNUSED_APPROVED_MATERIAL;
        classify as UNUSED_APPROVED_MATERIAL_SUFFICIENT,
        SOURCE_POOL_EFFECTIVELY_EXHAUSTED, or SOURCE_POOL_EXHAUSTED.
```

## The 169 WPM question

You confirmed 169 is your real rate, so I left `narration_words_per_minute` at **169** and
changed no runtime values. With 169 correct, WPM was never the problem — the **19-minute
floor** is what manufactures the 441-word shortfall:

| Floor | Word minimum @169 WPM | Post-cut 2,770 words |
|---|---|---|
| **19 min (current)** | 3,211 | short by 441 |
| 17 min | 2,873 | short by 103 |
| **16 min** | 2,704 | **passes** |

Your clean script is genuinely a ~16.4 minute video. The question is not how to reach 19
minutes from a six-claim source pool — it is whether 16 minutes is acceptable output for this
channel. If it is, set `target_runtime_range_minutes` to `[16, 35]` and this script passes on
content quality with no expansion. If you want 19-minute videos, the fix belongs at Research
and Outline — more approved claims before writing starts, not more words squeezed from six.

Your analytics can settle it: `analytics_db.py` already holds APV and retention per video.
Compare average view duration on your shorter videos against the longer ones before locking
a floor.
