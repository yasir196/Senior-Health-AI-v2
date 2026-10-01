# Master Production — Timestamp-First Redesign

Branch: `masterproduction`  
Scope: CapCut-ready production only. No final MP4 rendering.

## Locked architecture

The production workflow will move from pre-avatar estimated production timing to an avatar-first, timestamp-first workflow:

```text
06a_voice_script.md
→ Avatar generation
→ Avatar transcription (segment + word timestamps)
→ Master actual narration timeline
→ GUI Production Controller / Rule Engine
→ Timestamp-aware Production Planner
→ Production assets
→ CapCut-ready project
```

Avatar transcript timestamps are the timing authority. AI must not invent timing.

## 14-point implementation checklist

| # | Item | Status |
|---|---|---|
| 1 | Remove/skip pre-avatar estimated Production Plan as timing authority | TODO |
| 2 | Make avatar-first workflow the production path | TODO |
| 3 | Make avatar transcript timestamps the Master Clock / timing source of truth | PARTIAL — transcription already provides segment + word timestamps |
| 4 | Build Master Timeline directly from actual avatar timing | PARTIAL — `08_actual_timeline.csv` exists, but currently depends on `07_production_sheet.csv` |
| 5 | Run Production Planner only after actual timestamps exist | TODO |
| 6 | Add GUI Production Rule Controller | TODO |
| 7 | GUI supports add/edit/delete/enable/disable production rules | TODO |
| 8 | Add configurable timestamp duration rules (Hook images, normal images, etc.) | TODO |
| 9 | Keep Production Ratio user-controlled in GUI | PARTIAL — Avatar/AI Images/Stock/Overlays percentages already exist |
| 10 | Add configurable ratio tolerance / strict mode | TODO |
| 11 | Add section-specific overrides and rule priorities | TODO |
| 12 | Add deterministic Timestamp Controller; AI chooses semantic visual, not timing | TODO |
| 13 | Add timeline preview + QA for duration/gap/overlap/rule violations | TODO |
| 14 | Stop at CapCut-ready project; do not add final MP4 rendering | LOCKED |

## Current-code findings

The existing repository already has useful foundations:

- `avatar_timing.py` requests `verbose_json` transcription with segment and word timestamps.
- `08_actual_timeline.csv` already stores actual audio start/end/duration.
- `timeline_builder.py` explicitly treats `07_production_sheet.csv` as visual assignment metadata rather than timing authority.
- Current blocker: Avatar Timing still requires `07_production_sheet.csv`, so Production must currently run before avatar timing.
- Current GUI already stores Production Mix percentages in `production_settings.json`.
- Current GUI order is Generate Production Plan → Avatar Timing Sync. This must be reversed/refactored.

## Rule Engine requirements

Rules must be data-driven and GUI-editable, not hard-coded into prompts.

Initial rule examples:

- Hook image minimum duration: configurable (initial example 4s)
- Hook image maximum duration: configurable (initial example 5s)
- Normal image minimum duration: configurable (initial example 7s)
- Normal image maximum duration: configurable (initial example 8s)
- Avatar / AI image / stock / overlay target ratios: configurable
- Ratio tolerance: configurable
- Strict ratio mode: configurable
- Rule priority: configurable
- Rule enabled/disabled: configurable
- Section override: configurable

These values are defaults/examples only. GUI is the authority.

## Responsibility boundaries

- Transcript = what was actually spoken and when.
- Timestamp Controller = deterministic time boundaries.
- GUI Rule Engine = production constraints.
- AI Production Planner = what visual best supports each eligible timestamp window.
- Timeline Builder = deterministic final placement.
- CapCut Builder = editor handoff/execution.

## Migration rule

Do not delete the existing production path until the timestamp-first path is validated by tests. Introduce the new path behind explicit code/UI boundaries, then retire obsolete pre-avatar dependencies only after parity checks pass.

## First implementation target

Decouple avatar transcription and Master Timeline creation from the requirement that `07_production_sheet.csv` already exists. Preserve narration integrity checks against the approved voice script. After actual narration timing exists, generate production visual assignments against those timestamps.
