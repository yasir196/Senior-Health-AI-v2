# Human Editing Contract

Every audit record displayed in the dashboard must expose an **Edit / Correct** action.

Human-editable fields:
- Full thumbnail text (OCR correction)
- Video title pairing
- Category
- Psychological/pattern classification
- CTR
- Impressions

The UI must show, side by side where practical:
1. Original value
2. Current effective value
3. Edit/Correct control
4. Reason for correction
5. Reviewer note
6. Correction history

Corrections are append-only. The analyzer's original value is never silently destroyed. Future learning reads the effective value after human corrections while the audit view retains the original and complete history.

A correction must be visually labeled **HUMAN CORRECTED**. Unchanged source data remains **OBSERVED** and analyzer classifications remain **INFERRED**.

The database is owned by Thumbnail Pipeline and lives under `Thumbnail_Pipeline/outputs/db/`; it does not write to the existing V2 database.
