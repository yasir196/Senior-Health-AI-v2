from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def test_narrative_agent_requires_material_delta_for_3plus_recurrence():
    s = text('Agents/Narrative_QA_Agent.md')
    assert 'MATERIAL-DELTA TEST' in s
    assert 'Material delta vs primary' in s
    assert 'Merely changing the food/example/section' in s
    assert 'Material delta: NONE' in s

def test_opus_qa_does_not_accept_new_context_as_new_value():
    s = text('Templates/Writing/opus_narrative_qa.md')
    assert 'MATERIAL-DELTA TEST' in s
    assert 'different example, food, section, wording' in s
    assert 'MATERIAL DELTA `NONE`' in s

def test_writer_blocks_repeated_rule_reapplication_without_delta():
    s = text('Templates/Writing/opus_writer_prompt.md')
    assert 'core idea that would appear 3+ times' in s
    assert 'same safety/scope reminder attached to a new stage is not enough' in s

def test_retention_analyzer_uses_same_delta_contract():
    s = text('Templates/Writing/retention_structure_analyzer.md')
    assert 'MATERIAL DELTA VS PRIMARY' in s
    assert 'changed example, food, section, hypothetical, wording' in s

def test_runtime_prompt_carries_delta_gate():
    s = text('app.py')
    assert 'apply a MATERIAL-DELTA TEST to every post-primary occurrence' in s
    assert 'any post-primary occurrence with no concrete material delta must be CUT/MERGED' in s
