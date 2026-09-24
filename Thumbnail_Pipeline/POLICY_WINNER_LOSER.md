# Winner / Loser Learning Policy

## Normal next ideas
Only adequately sampled winner observations may seed normal future thumbnail ideas.

The unit of learning is not thumbnail image alone. The pipeline must inspect:
- immutable video title;
- OCR thumbnail text;
- title ↔ thumbnail-text overlap/complement;
- thumbnail hook type;
- visual/composition features;
- category;
- impressions and CTR.

The goal is to learn relationships such as: for a given title style/category, what kind of thumbnail visual and what kind of thumbnail text were associated with stronger channel performance.

## Losers
Losers are never promoted into normal future-idea priors. They are retained as negative evidence and receive a separate output named **Suggestion for Loser**.

A loser suggestion keeps the original title fixed and proposes a new test informed by adequately sampled winner patterns from the same category where possible.

## Guardrail
Winner/loser differences are observational associations, not causal proof. Low-impression observations remain excluded from learned rules.
