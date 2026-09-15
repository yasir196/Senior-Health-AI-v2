# CTR Packaging Fair-Comparison Audit Fix

Stage 4/5 promotion review was hardened after runtime validation.

- Stage 4 UI now exposes feature-cohort and comparison-cohort video/impression support.
- Stage 5 promotion audit requires clean post-snapshot attribution on both sides.
- Both cohorts require at least 3 videos and at least 1,000 impressions.
- An approximate 95% interval for the CTR percentage-point delta must exclude zero before promotion is enabled. This is a screening diagnostic, not causal proof.
- Reciprocal binary associations are deduplicated for Stage 5 review: the stronger side is the canonical candidate rather than treating A>B and B<A as two discoveries.
- Backend promotion enforces the same gate as the UI.
- Existing Analytics data and prior rule audit history are preserved.
