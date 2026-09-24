# Thumbnail Text Psychology / Pattern Taxonomy

Every OCR-readable thumbnail text receives explicit tags and an ordered pattern signature.

Supported primitives:
- `[PROBLEM]` — names pain, difficulty, symptom, friction, or unwanted state.
- `[ACTION]` — introduces an action verb or behavior.
- `[COMMAND]` — direct imperative: DO THIS, CHECK THIS, STOP, START HERE.
- `[QUESTION]` — asks an explicit or interrogative question.
- `[CURIOSITY]` — opens an information gap: HIDDEN, CLUE, NEXT, INSIDE, MISSED.
- `[CONTRAST]` — expectation reversal: BUT, NOT, ISN'T, VS.
- `[SPECIFICITY]` — narrows timing/order/count/context: FIRST, BOTH, BEFORE, AFTER, NIGHT.
- `[WARNING]` — caution/avoidance framing.
- `[IDENTITY_CONTEXT]` — audience/context cue such as AFTER 60 or AT NIGHT.
- `[NEUTRAL_STATEMENT]` — no supported psychological primitive detected.

Examples:
- KNEE PAIN? DO THIS FIRST → `[PROBLEM][QUESTION][SPECIFICITY][ACTION][COMMAND]`
- WHAT HAPPENS NEXT? → `[CURIOSITY][QUESTION]`
- FLOOR ISN'T STEP ONE → `[CONTRAST][SPECIFICITY]`
- ONE LEG OR BOTH? → `[QUESTION][SPECIFICITY]`

Winner learning must report the exact recurring signatures, their category, observation count, impressions, median CTR, title pair, and examples. Loser signatures remain negative/repair evidence and do not seed normal next ideas.

These labels describe framing mechanisms. Performance associations are observational, not proof of psychological causation.
