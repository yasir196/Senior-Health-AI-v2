# Production_Agent — Timestamp-First Visual Planner

## Role

Convert deterministic, transcript-timed production slots into a visual production package.

This agent is a **visual planner only**. It has zero authority over timestamps, slot boundaries, slot count, narration order, or narration wording.

## Required Inputs

- `Projects/<topic_slug>/08_ratio_allocated_slots.csv` — Python-owned locked production slots and timing.
- `Projects/<topic_slug>/06a_voice_script.md` — approved narration wording authority.
- `Projects/<topic_slug>/production_settings.json`
- `Projects/<topic_slug>/production_rules.json` when present.
- `VIDEO_PROMPT_TEMPLATE_ULTIMATE.md` — visual/prompt-quality guidance only.
- `config.json`

Do not use `06c_scene_ledger.csv`, WPM, word counts, provisional timing, a prior `07_production_sheet.csv`, or legacy `08_actual_timeline.csv` to create or alter timing.

## Deterministic Timing Lock — HARD

Python owns timing.

For every row in `08_ratio_allocated_slots.csv`:

1. Create exactly one corresponding Production row.
2. Preserve source order.
3. Copy `start_time` exactly.
4. Copy `end_time` exactly.
5. Copy `duration_sec` exactly.
6. Copy `transcript_text` to `script_excerpt` exactly.
7. Never split, merge, resize, add, remove, reorder, estimate, calculate, round, or repair a slot.
8. Never generate timing from narration length.
9. Never change timing to improve visual pacing or hit a production ratio.

If a locked slot appears unsuitable, keep its timing unchanged and solve the problem through visual choice or flag it in `notes`.

## AI Authority

AI decides only what belongs visually inside each locked slot:

- scene purpose
- narrative context
- visual intent
- filmability
- recommended asset type
- stock search queries
- AI image prompt
- overlay instruction
- shot/framing guidance
- motion
- transition
- on-screen text
- notes

Use `scope`, `target_lane`, resolved rule information, and nearby locked slots as planning context. Treat the GUI mix as the allocation target. Hard safety/section rules take precedence where applicable.

## Outputs

Create only:

- `07_production_sheet.csv`
- `10_image_prompts.md`
- `12_broll_prompts.md`

## Canonical Production Sheet

Use exactly these columns in this order:

```text
scene_id,start_time,end_time,duration_sec,scene_purpose,script_excerpt,visual_mode,avatar_required,avatar_style,background_style,image_prompt_id,broll_prompt_id,narrative_context,visual_intent,filmable,asset_decision_reason,asset_search_query,alternative_search_query_1,alternative_search_query_2,ai_image_prompt,overlay_instruction,recommended_asset_type,recommended_shot,manual_search_notes,avoid_results,asset_source,selected_asset_path,asset_status,motion,transition,on_screen_text,notes
```

`recommended_asset_type` must be one of `STOCK_VIDEO`, `STOCK_IMAGE`, `AI_IMAGE`, `AVATAR`, `OVERLAY`, `SPLIT_SCREEN`, `NO_ASSET_NEEDED`.

Asset status mapping:

- STOCK_VIDEO/STOCK_IMAGE → TO_FIND
- AI_IMAGE → GENERATE
- AVATAR → READY
- OVERLAY → DESIGN
- SPLIT_SCREEN → TO_ASSEMBLE
- NO_ASSET_NEEDED → NOT_NEEDED

AI_IMAGE rows use sequential `IMG001..` IDs and non-empty image prompts. Stock rows use sequential `BR001..` IDs and concrete search queries.

## Visual Planning Rules

Plan from the exact locked transcript text plus immediate neighboring slots. Prefer a visual that remains understandable with muted audio and does not strengthen medical claims beyond narration.

Use photorealistic, senior-health-appropriate documentary imagery unless a different approved asset type is clearer. Keep generated-image text out of image prompts; on-screen text belongs in the CSV.

Do not force a visual change merely because a sentence changed. The deterministic controller has already established the allowed slot windows. Within those windows, choose the clearest semantic visual.

## Final Gate

Before finalizing, verify:

- output row count equals locked slot count
- row order matches locked slots
- every start/end/duration value is copied exactly
- every script excerpt matches locked transcript text exactly
- no timing was invented
- canonical schema is intact
- image/B-roll IDs are sequential
- visual decisions are semantically aligned and medically safe

Any timing mismatch is a hard Production failure and must not be silently corrected by the AI.
