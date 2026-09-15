# Pre-Title Output Sanitization

Applied on top of `Senior_Health_AI_V3_4v_SOURCE_POOL_SUFFICIENCY`.
Result: **608 passed, 8 skipped, 0 failed** (was 583).

Title unchanged. `Can't Sit on the Floor After 60? Try These 3 Simple Exercises`
genuinely passes; the bug was entirely in parsing and rendering.

---

## Root cause

`_run_pre_title_check()` concatenates the checker's stdout **and** stderr:

```python
combined = "\n".join(x for x in [completed.stdout.strip(), completed.stderr.strip()] if x)
```

Codex echoes the prompt's own OUTPUT FORMAT block into that stream, and often repeats
its answer across both channels. `_extract_pre_title_line_protocol()` parsed every
`CHECK|` line it saw, with no notion of a placeholder.

The verdict cell of the echoed format line reads `PASS or REVIEW or HIGH RISK`, and
`_normalize_pre_title_result()` tests `if "HIGH" in v and "RISK" in v` first — so the
format line normalized to **HIGH RISK**. That is exactly why fake HIGH RISK rows appeared
beneath an overall PASS.

The screenshot shows three separate defects: the two placeholder rows, the three real rows
duplicated (rows 6–8 repeat rows 1–3), and `full suggested title` rendered as Same-DNA
suggestions under a PASS verdict — which the checker's own prompt forbids.

## Fixes (all in `app.py`)

**1. `_is_pre_title_placeholder()`** — deterministic detector for template tokens
(`check name`, `short reason`, `exact risky span…`, `minimal safer wording…`,
`full suggested title`, `one short sentence`), tolerant of angle brackets, casing and
whitespace. It also treats any cell enumerating two or more verdicts joined by "or" as a
format line rather than a verdict.

**2. `_sanitize_pre_title_result()`** — one contract applied to every parser path:

- any row or suggestion containing a placeholder is discarded;
- a REVIEW/HIGH RISK row must carry a concrete reason **or** risky span — an alarm with no
  evidence behind it is discarded;
- duplicate rows and duplicate suggestions are collapsed;
- an overall PASS renders no Same-DNA suggestions, per the checker's own instruction.

Wired at `_extract_pre_title_response()`, so JSON, line-protocol, markdown and nested
wrapper responses are all held to it. The nested path calls the raw variant so
sanitization runs exactly once.

**3. Echoed `OVERALL:` and `SUMMARY:` format lines** are now skipped rather than read, so a
stray `OVERALL: PASS|REVIEW|HIGH RISK` can no longer set the verdict.

**4. Prompt hardened** — placeholders now use `<angle brackets>`, the repeated CHECK and
SUGGESTION example lines are collapsed to one, and the instruction adds: do not repeat the
format block, do not output the placeholder words, do not restate your answer twice. This
reduces the contamination at source; the parser no longer depends on it.

**5. Tests** — `tests/test_pre_title_output_sanitization.py` (14 tests) replaying the exact
contaminated stream from the screenshot, plus: genuine HIGH RISK with evidence survives
intact, unevidenced alarms drop, a reason *or* a span is sufficient, PASS suppresses
suggestions, JSON responses are sanitized too, and a **closed-loop test** asserting every
`<placeholder>` in the shipped prompt is one the parser will reject.

That closed-loop test earned its place immediately: it failed on first run because the
reworded prompt introduced `exact risky span, or leave empty` while the token list still
held the old `…or blank` phrasing. Both forms are now covered.

## Verified against the reported output

Replaying the screenshot's stream:

```
before:  overall PASS, 8 rows (2 fake HIGH RISK, 3 duplicated), 3 placeholder suggestions
after:   overall PASS, 3 rows (all PASS, all real), 0 suggestions
```

And a genuine alarm is untouched:

```
overall HIGH RISK | 1 row | cure implication | risky span "reverse your diabetes"
suggestions: ["3 Habits That May Help Blood Sugar After 60"]
```

## Note

The sanitizer is strict by design: it drops a REVIEW/HIGH RISK row that arrives with no
reason and no risky span. If the checker ever legitimately wants to raise a concern it
cannot articulate, that row will now be discarded rather than shown. That is the right
trade — an unexplained alarm on a title is not actionable, and the overall verdict still
carries through regardless of the row.
