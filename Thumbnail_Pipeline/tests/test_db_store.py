from Thumbnail_Pipeline.db import store

def rec():
    return {"source":{"asset_id":"a","thumbnail_path":"x.jpg"},"observed":{"title":"T","thumbnail_text_full":"TXT","ctr":5.5,"impressions":1200},"inferred":{"category":"mobility","pattern_sequence":["one","two"]}}

def test_json_pattern_and_idempotent_save(tmp_path,monkeypatch):
    monkeypatch.setattr(store,"db_path",lambda:tmp_path/"db.sqlite3")
    a=store.save_audit(rec()); b=store.save_audit(rec())
    assert a==b
    assert store.effective_record(a)["pattern_inferred"]=='["one", "two"]'

def test_numeric_corrections_keep_types(tmp_path,monkeypatch):
    monkeypatch.setattr(store,"db_path",lambda:tmp_path/"db.sqlite3")
    a=store.save_audit(rec())
    store.add_correction(a,"ctr_observed","7.25")
    store.add_correction(a,"impressions_observed","2500")
    r=store.effective_record(a)
    assert r["ctr_observed"]==7.25 and isinstance(r["ctr_observed"],float)
    assert r["impressions_observed"]==2500 and isinstance(r["impressions_observed"],int)
