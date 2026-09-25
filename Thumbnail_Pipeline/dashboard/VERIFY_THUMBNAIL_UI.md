# Final Thumbnail Verification

The verifier checks whether a rendered loser-repair candidate implemented the **AI audit's structured edit contract**.

It does not invent a second design policy, regenerate the image, or reinterpret the user's original request.

Inputs:
1. rendered candidate;
2. structured AI audit/loser-repair contract;
3. machine observations and/or reviewed corrections.

Output: PASS / FAIL / NEEDS_REVIEW with expected vs observed values, failed requirements and unverifiable items. Missing detector evidence is NEEDS_REVIEW, never automatic PASS.
