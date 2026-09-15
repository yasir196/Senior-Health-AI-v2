from pathlib import Path

import v31_core

ROOT = Path(__file__).resolve().parents[1]


def test_narrative_qa_requires_semantic_progression_and_no_avd_prediction():
    text = (ROOT / 'Agents' / 'Narrative_QA_Agent.md').read_text(encoding='utf-8')
    assert 'Semantic Progression Gate' in text
    assert 'NEW`, `DEEPENS`, `RECAP`, or `REPEATS' in text
    assert 'WHOLE-SCRIPT RECURRENCE AUDIT' in text
    assert 'TITLE-PAYOFF TIMING GATE' in text
    assert 'RECAP / ENDING GATE' in text
    assert 'SAFETY-CONSOLIDATION GATE' in text
    assert 'Estimated AVD range' not in text


def test_writer_has_no_fixed_recap_story_or_loop_cadence():
    text = (ROOT / 'Agents' / 'Script_Agent.md').read_text(encoding='utf-8')
    assert 'Every 4-5 minutes, briefly remind' not in text
    assert 'Every 4-5 minutes, include one short real-world scenario' not in text
    assert 'Open a new curiosity loop every 60-90 seconds' not in text
    assert 'Strategic Recaps Only' in text
    assert 'no fixed cadence' in text.lower()


def test_auto_revision_delete_token_removes_text(tmp_path):
    project = tmp_path / 'p'
    project.mkdir()
    (project / '06_final_script.md').write_text('Keep this.\n\nDelete this repeated recap.\n\nEnd.', encoding='utf-8')
    (project / '14_narrative_qa.md').write_text('''Status: PASS WITH REVISIONS\n\n## Revision Patch\n### Revision 1\nSection: Recap\nCurrent Text: Delete this repeated recap.\nReplace With: [DELETE]\nReason: Semantic repetition.\nSeverity: HIGH\n''', encoding='utf-8')
    result = v31_core.apply_revision_patch(project, '14_narrative_qa.md')
    assert result.applied == 1
    revised = (project / '06_final_script.md').read_text(encoding='utf-8')
    assert 'Delete this repeated recap.' not in revised
    assert 'Keep this.' in revised and 'End.' in revised


def test_opus_writer_progression_lock_present():
    text = (ROOT / 'Templates' / 'Writing' / 'opus_writer_prompt.md').read_text(encoding='utf-8')
    assert 'Semantic Progression Lock' in text
    assert 'multiple ending cycles' in text
    assert 'never restore repetition' in text
