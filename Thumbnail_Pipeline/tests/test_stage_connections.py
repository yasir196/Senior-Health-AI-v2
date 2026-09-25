from Thumbnail_Pipeline.intelligence.runner import _split_by_category_median
from Thumbnail_Pipeline.intelligence.new_project_context import build_new_project_context, build_new_project_concept

def test_insufficient_category_does_not_break_winner_split():
    patterns={"category_patterns":{"mobility":{"status":"insufficient_observations","all":{"observations":1}}}}
    rows=[{"performance":{"ctr":5},"v2_analysis":{"hero_category":"mobility"}}]
    assert _split_by_category_median(rows,patterns)==([],[])

def test_new_project_without_provider_is_explicit_not_fake_search():
    c=build_new_project_context(title="T",topic="floor rise",category="mobility",winner_rows=[])
    assert c["youtube_discovery_status"]=="provider_not_connected"
    assert c["youtube_reference_count"]==0


def test_new_project_concept_connection_preserves_immutable_title():
    result=build_new_project_concept(title="LOCKED",topic="floor rise",category="mobility",winner_rows=[])
    assert result["context"]["immutable_title"]=="LOCKED"
    assert result["concept_direction"]["immutable_title"]=="LOCKED"
    assert result["concept_direction"]["evidence_status"]=="no_winner_evidence"
