# Research + Medical Gate 1 Final-Title Role Boundary Fix

## Problem
After Stage 1 correctly accepted an already-approved immutable anchor title, Research_Agent and Medical_Agent Gate 1 reopened the same title as a falsification/title-safety gate. This could stop the project because the title itself omitted clinical qualifiers or because a packaging phrase lacked direct evidence, even though those boundaries belonged in the content.

## Narrow production changes
1. `Agents/Research_Agent.md`
   - Research now consumes the Stage 1 approved production interpretation and tests downstream content propositions.
   - It must not re-adjudicate/falsify/repair/rank/replace the final title.
   - Unsupported downstream claims are bounded/rejected as claims, not converted into a title FAIL.
   - Removed the old Anchor Hypothesis Falsification Audit mandate.
2. `Agents/Medical_Agent.md`
   - Gate 1 is explicitly a content medical-safety gate, not a title-validation gate.
   - Missing title-level cautions/qualifiers become mandatory content boundaries, not reasons to fail the title.
   - Gate 1 can still FAIL genuine content-lane evidence/safety defects.
   - Removed the obsolete title-repair-blueprint requirement from Gate 1.
3. `app.py`
   - Replaced the old runtime command that told Research/MG1 to falsify the exact title and create `13a_title_repair_blueprint.json`.
   - Dispatcher is now short/generic and delegates policy to the two agent files.
4. `Knowledge/11_Content_Production_SOP.md`
   - Clarified that title validation is pre-project; after Create Project, Research/MG1 do not re-adjudicate the immutable approved title.

## Preserved behavior
- Anchor title remains exact and immutable.
- Research remains neutral and must surface weak/contrary evidence.
- Medical Gate 1 retains FAIL authority for genuine unsupported/unsafe content claims or instructions.
- Medical Gate 2 behavior is unchanged.
- Stage 1 behavior is unchanged.
- No title generation/repair stage was added.

## Validation
- `python -m py_compile app.py`: PASS.
- Full available suite excluding one environment-blocked Streamlit-import test: **583 passed, 8 skipped**.
- Full collection attempt: blocked only by `ModuleNotFoundError: streamlit` in `tests/test_pre_title_output_sanitization.py` in this container.
