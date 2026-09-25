import pytest
from Thumbnail_Pipeline.production import run_production_thumbnail

def spec():
    return {"immutable_title":"LOCKED","category":"mobility","composition":{"layout":"split","subject_placement":"right","text_placement":"left","safe_zone":"bottom_right_clear","thumbnail_text_candidates":["START HERE"]},"provenance":{"source":"test"}}
def gate(): return {"approved":True,"immutable_title":"LOCKED","schema_version":"0.4.0"}

class Backend:
    def __init__(self): self.calls=[]
    def generate(self,request):
        self.calls.append(request)
        return {"output_path":"Thumbnail_Pipeline/outputs/p/thumb.png","width":1280,"height":720,"immutable_title":"LOCKED"}

class Vision:
    def inspect(self,request):
        return {"layout_matches":True,"subject_placement_matches":True,"text_placement_matches":True,"safe_zone_clear":True}

def test_dry_run_does_not_persist_or_execute(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path); b=Backend()
    r=run_production_thumbnail(spec(),gate(),backend=b,selected_text="START HERE")
    assert b.calls==[] and r["receipt_path"] is None

def test_execute_persists_receipt(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path); b=Backend()
    r=run_production_thumbnail(spec(),gate(),backend=b,execute=True)
    assert len(b.calls)==1 and r["receipt_path"].startswith("Thumbnail_Pipeline/db/receipts/")

def test_visual_provider_can_finalize(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    r=run_production_thumbnail(spec(),gate(),backend=Backend(),visual_qa_provider=Vision(),execute=True)
    assert r["execution"]["downstream"]["stage"]=="finalized"
    assert r["receipt"]["finalized"] is True

def test_persisted_execution_blocks_duplicate(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path); b=Backend()
    run_production_thumbnail(spec(),gate(),backend=b,execute=True)
    with pytest.raises(ValueError):
        run_production_thumbnail(spec(),gate(),backend=b,execute=True)

def test_explicit_rerun_override_allows_second_execution(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path); b=Backend()
    run_production_thumbnail(spec(),gate(),backend=b,execute=True)
    run_production_thumbnail(spec(),gate(),backend=b,execute=True,allow_rerun=True)
    assert len(b.calls)==2

def test_missing_visual_provider_preserves_human_review(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    r=run_production_thumbnail(spec(),gate(),backend=Backend(),execute=True)
    assert r["execution"]["downstream"]["qa"]["status"]=="needs_human_review"

def test_title_is_preserved_end_to_end(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    r=run_production_thumbnail(spec(),gate(),backend=Backend(),visual_qa_provider=Vision(),execute=True)
    assert r["receipt"]["artifact"]["immutable_title"]=="LOCKED"
    assert r["execution"]["downstream"]["final_record"]["immutable_title"]=="LOCKED"

def test_no_v2_or_publish_side_effects(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    r=run_production_thumbnail(spec(),gate(),backend=Backend(),execute=True)
    assert not (tmp_path/"config.json").exists() and not (tmp_path/"Analytics").exists()
    assert r["publish_executed"] is False and r["v2_write_performed"] is False
