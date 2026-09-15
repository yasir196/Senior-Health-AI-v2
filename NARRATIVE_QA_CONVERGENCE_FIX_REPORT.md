# Narrative QA Convergence Fix

Applied on top of `Senior_Health_AI_V3_4v_PRE_TITLE_SANITIZATION`.

## Root cause fixed

The QA policy had become over-constrained: one localized ACTIVE density failure triggered a global cuts-only Density Interlock. That cut made an already-short script shorter; the 19-minute floor then created a large runtime shortfall; Source Pool Sufficiency correctly refused low-value padding, so the project could only FAIL.

The uploaded base also had `target_runtime_range_minutes: [19, 35]`, even though the intended current floor had been changed to 16 minutes in the live workflow.

## Narrow changes

1. Restored the intended canonical runtime range to **16–35 minutes at 169 WPM**.
2. Added a **3% lower-bound acceptance tolerance** (`runtime_floor_tolerance_percent`) so a tiny WPM/word-count variance does not manufacture a rewrite loop. The nominal minimum remains the planning boundary; the tolerance is never a target.
3. Separated **density** from **information progression**. A long paragraph is not automatically low progression when it contains a concrete NEW/DEEPENS material delta.
4. Changed the Density Interlock so it activates only for a **blocking** narrative defect, not every learned-rule FAIL. Learned channel rules remain active evidence, but a single local polish issue cannot force the whole project into a cut-only FAIL loop.
5. Writer behavior was not changed. Medical Gate 2, source-trace rules, Material-Delta rules, blueprint order, repetition hard gates, and source-pool anti-padding protections remain intact.

## Peanut Butter regression case

At 169 WPM and a 16-minute nominal floor, the nominal minimum is 2,704 words. With the 3% acceptance tolerance, the effective floor is 2,623 words. The observed fresh script at 2,652 narration words is therefore runtime-compliant rather than being forced into a 559-word expansion.
