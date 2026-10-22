# 10 — Script Writing SOP

> Permanent internal documentation. Senior Health YouTube Production System.
> This document is standalone and self-contained.
> Synchronized with `System/SYS_10_SCRIPT_STATE_MACHINE.json` v1.3.

---

## 1. Full Script Structure

| Section | Timing | Function |
|---------|--------|----------|
| Hook | 0–45s | Answer the thumbnail promise and deliver one concrete piece of value (see `05_Hook_Blueprints.md` and `SYS_05_HOOK_ENGINE.json`) |
| Body | Bulk | Deliver the promised items. Stakes, credibility, and mandatory triage are embedded beats placed where they support the content, with no fixed time slot |
| Recap + CTA | Final | Restate the strongest payoff, then a soft subscribe |

Priority principle: optimize retention within medical accuracy. Where retention conflicts with safety or evidence boundaries, safety and evidence take priority.

---

## 2. Section State Machine

| State | Time | Exit Condition | Next |
|-------|------|----------------|------|
| HOOK | 0–45s | Thumbnail promise answered and concrete value delivered | BODY |
| BODY | Bulk | All items delivered; embedded beats (stakes, credibility, triage when required) placed where they support content | RECAP |
| RECAP | Final | Strongest payoff restated + CTA | END |

Body rules:
- Mandatory triage precedes any movement or action instruction.
- Each evidence module, mechanism, and limitation attaches to the item it supports. Do not create a standalone evidence or "can/cannot" block before the body.
- Place only a one-sentence scope boundary before the first demonstration.

---

## 3. Invariants

| ID | Rule | Severity |
|----|------|----------|
| I1 | Open a loop only when a real question exists; close every loop (no fixed 60–90s cadence) | Advisory |
| I2 | Item order serves the viewer; the strongest item may come first when it delivers the thumbnail payoff | Advisory |
| I3 | Strongest item last and pre-teased (optional; never delay the thumbnail answer for it) | Advisory |
| I4 | At least one actionable takeaway | Block |
| I5 | Payoff matches title | Block |
| I6 | Clinician caveat present | Block |
| I23 | First practical value by 3:00 (exception: mandatory triage, with the reason recorded in the outline under "Time to first practical value") | Block |

The full invariant list (I1–I23) lives in `SYS_10_SCRIPT_STATE_MACHINE.json`. If this table and SYS_10 ever disagree, SYS_10 is authoritative.

---

## 4. Transitions

End each major section by pointing to the next needed decision or question. Use verbal signposts ("before I show you the first move, here is the one check that matters"). Open a new loop only when a real question exists; do not open loops just to fill a cadence.

---

## 5. Retention Methods

1. Short sentences; sensory language.
2. Deliver concrete value early. Withhold depth, never the core answer to the thumbnail promise.
3. Open loops adaptively and close every one.
4. The strongest item may lead when it answers the thumbnail; otherwise, order items for clarity.
5. Integrate, don't lecture: explain a technical term in one plain sentence where it is first needed, and attach each measurement or study detail to the point it supports.
6. Use a pattern interrupt so no uninterrupted explanation exceeds three minutes.
7. Mini stories are optional, evidence-serving, and clearly labeled as hypothetical. Recaps are strategic, never time-based.

---

## 6. Viewer Engagement

- Direct second-person address
- Rhetorical questions
- Physical participation prompts (only when safe and within the approved cautions)
- Symptom checklists that invite self-recognition (plain language, never diagnostic)

---

## 7. Value-Add Framework

Every video must deliver at least one genuinely useful, evidence-backed, actionable takeaway that justifies the runtime and the promise. The payoff must match the title (invariant I5). Bait-and-switch is prohibited and blocked at QA. Runtime is ADVISORY ONLY — NON-BLOCKING; never pad, repeat, or add low-value material to reach a duration.

---

## 8. Quality Checklist

- [ ] Opening answers the thumbnail promise and delivers concrete value within the first 30 seconds
- [ ] First practical value by 3:00, or the triage reason is recorded
- [ ] Mandatory triage and cautions are intact and placed before any action instruction
- [ ] Every claim traces to an approved source; no new statistics
- [ ] Evidence is attached to the item it supports, with no standalone lecture block
- [ ] One clear actionable takeaway present
- [ ] Payoff matches the title promise
- [ ] Clinician caveat included; host not presented as a clinician when `doctor_mode` is false
- [ ] Every opened loop is closed
- [ ] No uninterrupted explanation longer than three minutes

---

*End of document.*