# Thumbnail Text Pattern Discovery

The pipeline does **not** start from a fixed psychology vocabulary such as PROBLEM, ACTION, COMMAND, CURIOSITY, or WARNING.

Patterns are discovered from eligible channel evidence in `ocr.text`, paired with title, category, CTR and impressions. Current discovery extracts recurring 1/2/3-word phrases plus neutral structural markers such as question mark, exclamation mark and word count.

Requirements:
- minimum observations come from `config/intelligence.json`;
- labels are descriptive channel-data discoveries, not psychological truths;
- unclassified text remains visible;
- human review may rename/correct discovered interpretations;
- winner associations are observational, not causal;
- loser patterns remain in the repair lane and do not seed normal new-project priors.
