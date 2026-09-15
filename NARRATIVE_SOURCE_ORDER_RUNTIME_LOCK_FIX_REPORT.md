# Narrative QA Source / Order / Runtime Lock Fix

Base: `Senior_Health_AI_V3_4v_FIXED.zip` (Claude-fixed build).

## Narrow changes

1. **Source-Bound Delta Gate**
   - Every factual `NEW` / `DEEPENS` beat now needs an explicit approved source trace.
   - Useful/plausible/logical inference is not sufficient.
   - New mechanisms, comparisons, generalizations, product-variability claims, prevalence/risk claims, or other fresh factual propositions cannot be kept without explicit approved support.

2. **Blueprint Order Gate**
   - Narrative QA must compare current major section/beat order with `05_script_outline.md` and approved `retention_structure_analysis.md` when present.
   - The outline is the default order authority; a changed order requires explicit authorization for that specific reorder.
   - Misplaced major sections cannot PASS.

3. **QA No-Runtime-Invention Lock**
   - Runtime never protects repetition.
   - If required semantic cuts push the script below the configured minimum, Narrative QA must FAIL and route back to Writer/Outline.
   - Narrative QA may not invent new factual teaching merely to regain runtime.

## Preserved

- Claude exact PASS gating and production-chain fixes.
- Independent Narrative QA vs Retention Structure policy.
- Existing Material-Delta logic.
- ACTIVE channel-rule verification.
- Runtime boundary logic and anti-padding behavior.
- Medical Gate 2 remains the downstream medical verification gate.
