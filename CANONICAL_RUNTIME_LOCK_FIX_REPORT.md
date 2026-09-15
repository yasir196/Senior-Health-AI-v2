# Canonical Runtime Lock

Applied on top of `Senior_Health_AI_V3_4v_TEMPLATE_CONTRACT_FIX`.
Result: **569 passed, 8 skipped, 0 failed** (was 558).

---

## What the diagnosis got right, and one correction

The convergence loop is real and structural. But Narrative QA was **not** inventing an
independent WPM. It read `config.json` faithfully:

```
narration_words_per_minute = 169
target_runtime_range_minutes = [19, 35]
19 × 169 = 3,211  ← exactly the floor the QA reported
```

The second, competing authority was upstream, in `System/SYS_10_SCRIPT_STATE_MACHINE.json`:

```
default_runtime.minimum_minutes = 18       maximum_minutes = 23
estimated_speaking_rate_wpm.default = 145  (acceptable_range 130–160)
estimated_word_count_range_default.target_words_at_145_wpm = 2900
qa_failure_rules.runtime_outside_target_without_override = fail
```

Hardcoded, never read from config. That is where the writer-facing ~145 WPM / ~2,900-word
basis came from. Two authorities, ~450 words apart — the exact size of the add-then-cut
oscillation.

There were also three divergent hardcoded fallbacks in code: `145` in `v31_core.py` (×3)
and `app.py:830`, and **`150`** in `app.py:1297`. Inert while config supplies the key, but
the same bug waiting for a config without it.

Worth noting: 169 WPM sits above SYS_10's own stated acceptable ceiling of 160.

## Fixes

**1. One canonical authority (`v31_core.py`)**

- `RuntimeProfile` + `canonical_runtime(config)` — the single place narration-word bounds
  are derived. `DEFAULT_NARRATION_WPM = 145` is now the one shared fallback.
- `runtime_within_canonical_range(words, config)` — the runtime PASS condition.
- `runtime_config_conflicts(config)` — detects any second runtime authority.
- Every read site rewired: `validate_final_script`, `script_quality_metrics`,
  `app.py:830`, `app.py:1297`. The `150` default is gone.

**2. `SYS_10_SCRIPT_STATE_MACHINE.json` stops being an authority**

`default_runtime` now carries `authority: "config.json is the canonical runtime
authority…"`, `fallback_only: true`, and its old numbers renamed to `fallback_*`. Added a
`canonical_runtime_lock` block with the pass condition, the prohibited moves, and the
source-pool-exhaustion rule.

**3. Prompt layer — three new Narrative QA rules** (agent, Opus template, `app.py` prompt,
output template)

- **26 · Canonical Runtime Lock** — config.json only; never adopt a WPM or window from a
  writer package, System JSON, template, or prior report; state the values used.
- **27 · Runtime-Pass Precedence** — apply required cuts first, then measure. Inside the
  canonical range → runtime is PASS, no further length change, no drift toward midpoint.
  Runtime may never demand restored repetition or low-value material, and never overrides
  a required semantic cut.
- **28 · Source Pool Exhaustion Escalation** — below minimum after cuts, QA must classify
  the cause:
  - `UNUSED_APPROVED_MATERIAL` → name it, FAIL, route to Writer/Outline.
  - `SOURCE_POOL_EXHAUSTED` → state the shortfall, escalate as a runtime-configuration
    decision, and **do not** request another redevelopment cycle over the same pool.

  This is the loop-breaker. Old rules 7 and 10 routed *every* shortfall to the Writer;
  they are now scoped to the cause that is actually resolvable there.

**4. UI** — `render_runtime_authority_notice()` warns in the Writer Workspace whenever a
second runtime basis is detected.

**5. Tests** — `tests/test_canonical_runtime_lock.py` (11 tests): profile derivation,
target clamping, malformed-config fallback, the pass condition, no divergent hardcoded
defaults, SYS_10 deference, prompt-surface coverage, and a positive test proving the
conflict detector fires on a real second authority.

## Not changed, on purpose

`config.json` values are untouched, and the repetition / source-trace / blueprint-order
gates are untouched. Which runtime basis is correct is an editorial decision, not a bug.

## The decision this leaves you

The lock makes the conflict impossible to reintroduce; it does not pick the numbers.
For the ~2,720-word post-cut script:

| Configuration | Word window | 2,720 words | Passes? |
|---|---|---|---|
| **Current** — 169 WPM, 19–35 min | 3,211–5,915 | 16.09 min | No |
| 145 WPM, 19–35 min | 2,755–5,075 | 18.76 min | No — 35 words short |
| **145 WPM, 16–35 min** | 2,320–5,075 | 18.76 min | **Yes** |

The third row is the writer package's own stated basis. Setting `narration_words_per_minute`
to `145` and `target_runtime_range_minutes` to `[16, 35]` makes the current clean script
pass on content quality alone, with no Writer redevelopment and no gate loosened.

Before committing to it, measure your actual delivery rate: take a rendered ElevenLabs/HeyGen
chunk, count its spoken words, divide by its real duration. `avatar_timing.py` already
produces exactly this from `08_actual_timeline.csv`. Set the canonical WPM to the measured
value rather than either inherited number — then every stage is calibrated to the voice you
actually ship.
