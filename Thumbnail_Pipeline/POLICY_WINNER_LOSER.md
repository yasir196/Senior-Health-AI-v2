# Winner / Loser Learning Policy

## New projects / new videos — winner-only prior

Every new project or new video must build its thumbnail direction from **eligible winner evidence only**.

The learning unit includes:
- immutable video title;
- full thumbnail text;
- title ↔ thumbnail-text relationship;
- discovered text mechanisms from channel data;
- visual/composition features;
- category;
- CTR, impressions, attribution status, and evidence weight.

### Selection order
1. Prefer eligible winners from the same V2 category.
2. If same-category winner evidence is unavailable or insufficient, return **INSUFFICIENT_WINNER_EVIDENCE** for the learned prior.
3. Do not silently fall back to loser patterns.
4. Do not use loser text, loser composition, loser visual direction, or loser discovered mechanisms as positive priors.
5. The immutable new-project title remains the governing title; winner evidence guides thumbnail treatment, not title replacement.

## Losers — repair lane only

Losers are retained as negative evidence and are allowed only in the dedicated **Suggestion for Loser / Repair** lane.

A loser may be compared with eligible same-category winners to diagnose what to change. A loser must never seed:
- a normal new-project concept;
- a new-video thumbnail direction;
- a winner pattern;
- a positive recommendation prior.

## Isolation rule

Normal new-project generation consumes the winner-only output. Loser records and loser-repair outputs are not accepted as inputs to the new-project prior.

## Guardrail

Winner/loser differences are observational associations, not causal proof. Configured impression eligibility and V2 attribution/evidence rules still apply.
