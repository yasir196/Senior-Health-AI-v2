from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_agent_requires_historical_example_audit_trail():
    text=(ROOT/'Agents'/'Thumbnail_Agent.md').read_text(encoding='utf-8')
    assert 'Historical Example Audit Lock' in text
    assert '## Historical Channel Examples Used' in text
    assert 'NO MATCHING HISTORICAL EXAMPLES AVAILABLE' in text
    assert 'exact historical thumbnail text' in text
    assert 'CTR' in text and 'impressions' in text
    assert 'Adapted in this project:' in text
    assert 'Traceability Lock' in text

def test_thumbnail_command_requires_audit_trail():
    text=(ROOT/'app.py').read_text(encoding='utf-8')
    assert 'Historical Channel Examples Used' in text
    assert 'NO MATCHING HISTORICAL EXAMPLES AVAILABLE' in text
