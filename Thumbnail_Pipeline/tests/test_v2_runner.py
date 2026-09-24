from Thumbnail_Pipeline.intelligence import v2_runner

class FakeAdapter:
    def __init__(self,path): self.path=path
    def to_intelligence_rows(self): return [{"performance":{"title":"T","ctr":5.0,"impressions":1000,"evidence_weight":0.5},"ocr":{"text":"TEXT"},"v2_analysis":{"hero_category":"mobility"}}]

def test_v2_runner_uses_direct_read_only_adapter(monkeypatch,tmp_path):
    monkeypatch.setattr(v2_runner,"V2AnalyticsReadOnlyAdapter",FakeAdapter)
    monkeypatch.setattr(v2_runner,"run_intelligence",lambda rows,output_dir="intelligence":{"rows_seen":len(rows)})
    result=v2_runner.run_from_v2(tmp_path/"analytics.db")
    assert result["source"]=="v2_analytics_read_only"
    assert result["source_rows"]==1
    assert result["rows_seen"]==1
