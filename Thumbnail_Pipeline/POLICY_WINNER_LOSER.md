# Winner / Loser Learning Policy

## New projects / new videos
New-project thumbnail direction uses **eligible winner evidence only** as internal channel learning.

Selection order:
1. Prefer eligible winners from the same V2 category.
2. If none exist in that category, select the strongest eligible winner category from observed channel evidence.
3. Never fall back to loser patterns.
4. If the channel has no eligible winner evidence at all, return **NO_WINNER_EVIDENCE**.
5. The supplied project title remains immutable.

External YouTube references may then broaden the concept: same-topic first, then same-category, across channels. Inspect title + thumbnail together. External references do not turn losers into positive priors and do not replace the immutable title.

## Losers — repair lane only
Losers are negative/repair evidence. Compare them with eligible same-category winners when diagnosing an edit. They must not seed a normal new-project concept or positive recommendation prior.

## Guardrail
Winner/loser differences are observational associations, not causal proof. Configured impression eligibility and V2 attribution/evidence rules apply.
