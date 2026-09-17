# Population applicability backfill

This migration is intentionally conservative. Existing claim wording and medical policy are not changed.

- `CLM_KIWI_SLEEP_ROUTINE`: explicit library limitation records ages 20–55 and not senior-specific; governing type is `outcome_study`.
- `CLM_SLEEP_CARE_CAVEAT`: governing type is `guideline`; guideline type does not imply senior-specific scope.
- `CLM_KIWI_ALLERGY_CAVEAT`: governing type is `outcome_study`; required population metadata is not explicitly recorded in the repository, so status is `metadata_incomplete`.
- `CLM_KIWI_NUTRITION_CAUTION`: governing type is `descriptive_compositional`; study population and extrapolation are type-governed nulls.
- `CLM_DASH_BP_SUPPORT`: governing type is `outcome_study` by material-source precedence; required population metadata is not explicitly recorded in the repository, so status is `metadata_incomplete`.
- `CLM_DASH_SODIUM_BP`: governing type is `outcome_study`; required population metadata is not explicitly recorded in the repository, so status is `metadata_incomplete`.
- `CLM_OATS_CVD_SUPPORT`: governing type is `outcome_study`; pooled population metadata is not explicitly recorded in the repository, so status is `metadata_incomplete`.

No row is assigned `senior_specific=true` by template or source type. Missing values are not inferred. Phase A does not perform network source resolution.
