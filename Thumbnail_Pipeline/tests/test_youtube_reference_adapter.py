from Thumbnail_Pipeline.adapters.youtube_reference import collect_references
from Thumbnail_Pipeline.intelligence.new_project_context import build_new_project_context

class Fake:
    def search(self,query,limit=12):
        if query=="floor rise": return [{"video_id":"a","channel_name":"Other","video_title":"Floor Rise","thumbnail_url_or_path":"thumb-a","views":1000}]
        return [{"video_id":"b","channel_name":"Other2","video_title":"Mobility","thumbnail_url_or_path":"thumb-b","views":2000}]

def test_collects_topic_then_category_cross_channel():
    rows=collect_references(provider=Fake(),topic="floor rise",category="mobility")
    assert [x["search_scope"] for x in rows]==["same_topic","same_category"]
    assert all(x["outlier_status"]=="not_claimed" for x in rows)

def test_new_project_context_combines_winners_and_youtube(monkeypatch):
    monkeypatch.setattr("Thumbnail_Pipeline.intelligence.new_project_context.analyze_youtube_reference_thumbnails",lambda refs:[{**r,"thumbnail_analysis_status":"analyzed"} for r in refs])
    winners=[{"performance":{"title":"Winner","ctr":8,"impressions":10000},"ocr":{"text":"FIRST"},"v2_analysis":{"hero_category":"mobility"}}]
    c=build_new_project_context(title="New title",topic="floor rise",category="mobility",winner_rows=winners,youtube_provider=Fake())
    assert c["primary_learning_source"]=="channel_winners"
    assert c["youtube_reference_count"]==2
    assert c["immutable_title"]=="New title"
