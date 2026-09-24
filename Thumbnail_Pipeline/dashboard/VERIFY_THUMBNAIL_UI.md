# Final Thumbnail Verification

After the user renders a thumbnail in any image generator, the pipeline can verify the result against the exact requested constraints.

## Purpose
Answer one question: **Did the rendered thumbnail actually implement what the user requested?**

This stage does not generate, regenerate, or rewrite the image prompt.

## Inputs
1. Final rendered thumbnail.
2. The exact requested thumbnail contract/prompt.
3. Machine observations and/or human corrections from the audit layer.

## Required output
- Overall verdict: PASS / FAIL / NEEDS_REVIEW
- Requirement-by-requirement result
- Expected value
- Observed value
- Exact failed requirements
- Items that could not be reliably verified

## Rules
- Verify only explicit requested constraints; do not invent new design rules.
- Exact thumbnail text must be checked as exact text when OCR/human-corrected text is available.
- Composition constraints such as 16:9, human count, face count, presenter position, text zone, hero count, and timestamp-safe zone are checked when requested.
- Explicit forbidden items are checked individually.
- Missing detector evidence is NEEDS_REVIEW, never automatic PASS.
- Human correction can override an incorrect machine observation through the existing audit/correction layer.
- A FAIL explains what was not implemented; it does not silently modify the user's prompt.
