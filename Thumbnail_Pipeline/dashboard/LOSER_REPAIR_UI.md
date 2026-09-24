# Loser Repair UI

Each loser card must show, in this order:

1. Original thumbnail preview
2. Immutable video title
3. Full original thumbnail text
4. Why it was placed in the lower-CTR group, with evidence
5. **Suggestion for Loser**
6. Proposed replacement thumbnail text
7. Proposed visual/composition direction
8. **Editable Image Prompt** — a multiline editor, never hidden
9. **Generate Now** button
10. Generated candidate preview + Save as Candidate / Regenerate

## Fast workflow
Human can edit the generated prompt before generation. Generate Now sends exactly the currently visible editor value plus the required thumbnail contract to the configured image-generation provider. It must not silently rewrite the human-edited prompt.

The generated image is a candidate only. It must not replace historical evidence or an existing published thumbnail automatically.

## Required audit fields
- loser audit id
- source title
- source full thumbnail text
- suggestion basis / winner references
- proposed text
- prompt before human edit
- prompt actually sent
- provider/model identifier
- generation timestamp
- generated candidate path
- human decision
