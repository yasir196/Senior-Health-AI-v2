# Topic Validation Role-Boundary Fix

- Removed the long topic-specific Stage-1 runtime prompt from `app.py`; the dispatcher is now generic and delegates policy to `Agents/Outlier_Agent.md`.
- Preserved the immutable anchor title and parser-scaffold handling.
- Clarified that titles entering Stage 1 are already approved upstream and Stage 1 is not a second title-repair/title-approval gate.
- Stage 1 still performs deep topic research to establish a defensible production payoff, demand, boundaries, and safety.
- Unsupported extensions are bounded/excluded. A Stage-1 FAIL now requires a genuine topic-level problem rather than a parser gap or an upstream-approved packaging quantifier alone.
- No pre-title artifact or pipeline dependency was added.
