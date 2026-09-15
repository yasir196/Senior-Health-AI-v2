# Weakness Fixes Applied — Senior Health AI V3.4v

Baseline before fixes: pytest **could not collect** (2 files with hardcoded absolute
paths). With those ignored: **18 failed, 526 passed**.

After fixes: **543 passed, 8 skipped, 0 failed.**

---

## P0-1 — Medical/editorial gates were not enforced in code

`v31_core.py :: stage_ready("Speech Optimizer")` only checked that
`06_final_script.md` existed and was non-empty. It did not read Narrative QA or
Medical Gate 2 at all.

This mattered more than it looks. `production_lock()` deliberately gates only on
`06a_voice_script.md` — that design is correct *provided* the voice script can only
be produced by the Speech Optimizer, which is itself gated. With the Speech
Optimizer gate removed, the whole chain was open: a project with a **FAILED Medical
Gate 2 could reach Production**.

**Fixed:** `stage_ready("Speech Optimizer")` now requires Narrative QA **and**
Medical Gate 2 to report exactly `PASS`. Conditional verdicts
(`PASS WITH REVISIONS` / `PASS WITH SUGGESTIONS`) are rejected — unapplied
revisions must be resolved and the gate rerun.

`production_lock()` was left unchanged: three existing tests assert it checks only
the voice script, and that is the intended design once the upstream gate is back.

**Residual loophole closed separately:** a hand-written or externally copied
`06a_voice_script.md` still bypasses the chain. The Production page now shows a
blocking-red advisory whenever Narrative QA or Medical Gate 2 is not at PASS.

## P0-2 — Test suite could not run

Three test files read source files from absolute paths left over from old
generation sessions:

- `tests/test_retention_hook_payoff_continuity_guardrail.py` → `/tmp/shai_retention_continuity_rule_noubohsg/...`
- `tests/test_retention_one_pass_lock.py` → `/tmp/shai_final_onepass_jdbza3nk/...`
- `tests/test_retention_structure_viewer_language_guardrail.py` → `/tmp/retention_viewer_language_fix_plz5_o_d/...`

The first two broke pytest **collection**, so the entire suite aborted — every other
guardrail in the repo had been silently inactive since they were added.

**Fixed:** all three now resolve via `Path(__file__).resolve().parents[1]`, the
pattern already used by every other test file.

## P0-3 — Two real regressions the dead suite had already caught

`test_auto_stage_progression` and
`test_speech_optimizer_requires_both_exact_pass_and_refreshes` encoded the correct
gate contract and were failing. Both pass now that P0-1 is fixed. No test changes
were needed — the code was wrong, not the tests.

## P1-1 — SQLite concurrency

`analytics_db.py :: _db_connect()` opened the database with no journal mode, no busy
timeout and default thread affinity. Streamlit reruns on every interaction while
YouTube sync / bulk CSV import hold write transactions → `database is locked`.

**Fixed:** `timeout=30.0`, `check_same_thread=False`, `PRAGMA busy_timeout=30000`,
`PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`. WAL switching is wrapped so
a read-only or network path degrades to the old rollback journal instead of
crashing.

## P1-2 — CapCut overlay tests encoded a superseded design (4 tests)

`tests/test_capcut_export.py` imported `TEXT_OVERLAY_MAIN_COLOR`, a constant that no
longer exists, and asserted the old single-white palette. The export has since moved
to a per-Overlay-Type high-contrast palette (`TEXT_OVERLAY_TYPE_STYLES`): main text
colour, card background and separator colour are all type-driven, and separator
background alpha is now `1.0`.

This was test rot, not a code bug — so the **tests** were updated, and they were
updated to derive expectations from `TEXT_OVERLAY_TYPE_STYLES` rather than hardcode
new literals. The guardrail still proves the export applies the correct colour per
type; it just no longer breaks the next time the palette is tuned.

## P1-3 — Narrative QA guardrail tests encoded a weaker old policy (3 tests)

Tests asserted the string `"Preserve approved Retention Structure Analysis
decisions"`. The agent and Opus template have since been **tightened** to
`"Treat Retention Structure Analysis as prior editing context, NOT proof"` — prior
decisions must now survive an independent current-script audit.

Reverting the prompts would have been a downgrade, so the assertions were updated to
the current, stricter contract.

## P1-4 — Fixture-dependent tests (8 tests)

`test_production_narrative_planning.py`, `test_image_prompt_finalization_regression.py`
and one case in `test_content_promise_bond.py` audit real project folders under
`Projects/` that are not shipped. They failed on every clean checkout, masking real
failures.

**Fixed:** they now `skip` with an explicit reason when the fixture is absent and run
normally when it is present. They currently show as **8 skipped**.

> Follow-up worth doing: commit minimal fixture copies under `tests/fixtures/` so
> these become real regression tests again instead of permanently skipped ones.

## P2 — Drift and hygiene

- **Version strings:** `app.py` hardcoded "V3.3" in four places while
  `config.json` said `system_version: 3.4`. Now derived from config via a single
  `system_version()` helper.
- **CapCut schema drift:** `config.capcut_supported_schema` claimed
  "CapCut Desktop 6.x-9.x plain-JSON draft schema"; the exporter actually emits the
  8.7 Windows multi-file bundle. Config corrected to match the code.
- **Dependency pinning:** `requirements.txt` had open-ended `>=` only. Upper bounds
  added so a major release of streamlit/pandas/openai/Pillow cannot break the app
  silently. `pytest` added.
- **Dead code:** `capcut_export_old.py` (93 KB, imported nowhere) deleted.
  `__pycache__/` and `.pytest_cache/` removed.

---

## Not fixed — needs your decision

1. **Live OAuth credentials.** `Analytics/youtube_oauth_credentials.json` (real
   `client_secret`) and `youtube_oauth_token.json` (real `refresh_token`) were inside
   the uploaded zip. They are **excluded from this deliverable**, but the originals
   on your machine are still valid — **rotate them in Google Cloud Console**, then
   re-authorize from the Config page. `.gitignore` already excludes them; the zip
   packaging step does not.
2. **93 broad `except Exception`** (31 in app.py, 21 in analytics_db.py, 18 in
   youtube_api_sync.py), 10 of them silent `pass`. These can make a partially-failed
   analytics sync report success and feed incomplete data into the learning engine.
   Fixing properly means deciding, per site, what should surface to the UI — too
   invasive to do blind.
3. **`TEXT_OVERLAY_BACKGROUND_OPACITY = 0.75`** in `capcut_export.py` is now dead:
   the code sets `background_alpha = 1.0` directly. Either delete the constant or
   make the code use it — currently it misleads anyone tuning the overlay look.
4. **Whisper alignment chain has no manual escape.** If avatar transcription drops
   below the 92% threshold, `08_actual_timeline.csv` never gets built and CapCut
   export is blocked with no override path. Worth adding a manual timing entry mode.
5. **Model IDs** `claude-opus-4.8` and `gpt-5.6-luna` in `config.json` — verify these
   are valid API strings, otherwise those stages fail at runtime.
