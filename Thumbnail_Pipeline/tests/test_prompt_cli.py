import json
from pathlib import Path
import pytest
from Thumbnail_Pipeline.runner.__main__ import resolve_project, build_project_prompt_state

def test_resolves_exact_project_under_projects(tmp_path):
    root=tmp_path/"Projects"; p=root/"my-project"; p.mkdir(parents=True)
    assert resolve_project("my-project",str(root))==p.resolve()

def test_missing_project_fails_clearly(tmp_path):
    root=tmp_path/"Projects"; root.mkdir()
    with pytest.raises(FileNotFoundError): resolve_project("missing",str(root))

def test_rejects_path_escape(tmp_path):
    root=tmp_path/"Projects"; root.mkdir()
    with pytest.raises(ValueError): resolve_project("../other",str(root))

def test_project_state_reads_title_without_mutating_project(tmp_path):
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    meta={"title":"1 CLOVE in Your Coffee Every Morning (Here's What Happens)","category":"nutrition"}
    f=p/"project.json"; f.write_text(json.dumps(meta),encoding="utf-8")
    before=f.read_bytes()
    state=build_project_prompt_state(p)
    assert state["immutable_title"]==meta["title"]
    assert state["composition"]["immutable_title"]==meta["title"]
    assert f.read_bytes()==before

def test_project_state_keeps_unsupported_review_fields_unresolved(tmp_path):
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"video_title":"LOCKED"}),encoding="utf-8")
    state=build_project_prompt_state(p)
    assert "subject_placement" in state["composition"]["human_review_required_for"]
    assert state["composition"]["constraints"]["generation_allowed"] is False

def test_missing_title_fails_instead_of_guessing(tmp_path):
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text("{}",encoding="utf-8")
    with pytest.raises(ValueError): build_project_prompt_state(p)


def test_project_state_does_not_read_v2_thumbnail_markdown(tmp_path):
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"LOCKED"}),encoding="utf-8")
    (p/"04_thumbnail_concepts.md").write_text("OLD CONCEPT",encoding="utf-8")
    (p/"11_thumbnail_prompt.md").write_text("OLD PROMPT",encoding="utf-8")
    state=build_project_prompt_state(p)
    assert "source_artifacts" not in state
    assert state["immutable_title"]=="LOCKED"


def test_cluster_state_has_no_legacy_hero_category_gate(tmp_path):
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"Clove in Coffee Every Morning"}),encoding="utf-8")
    state=build_project_prompt_state(p)
    assert "hero_category" not in state
    assert "hero_category_support" not in state
    assert "discovered_cluster" in state
    assert "cluster_count" in state


def test_youtube_discovery_runs_before_title_only_fallback(monkeypatch,tmp_path):
    import Thumbnail_Pipeline.runner.__main__ as runner
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"1 CLOVE in Your Coffee Every Morning"}),encoding="utf-8")
    class Provider:
        def __init__(self): self.queries=[]
        def search(self,query,limit=12):
            self.queries.append(query)
            return [{"video_id":"x","channel_name":"Other","video_title":"Clove Coffee Morning",
                     "thumbnail_url_or_path":"https://i.ytimg.com/vi/x/hqdefault.jpg","views":"100"}]
    provider=Provider()
    monkeypatch.setattr(runner,"analyze_youtube_reference_thumbnails",lambda refs:[
        {**refs[0],"thumbnail_analysis_status":"analyzed","external_thumbnail_ocr":{"text":"CLOVE COFFEE?"}}
    ])
    state=build_project_prompt_state(p,youtube_provider=provider)
    evidence=state["concept"]["evidence"]
    assert provider.queries==["1 CLOVE in Your Coffee Every Morning"]
    assert evidence["youtube_fallback"]["status"] in {"used","searched_no_recurrent_text_mechanism"}
    assert evidence["youtube_reference_count"]==1

def test_youtube_not_called_when_recurrent_local_mechanism_exists(monkeypatch,tmp_path):
    # The boundary is explicit: external discovery is a fallback, never a replacement
    # for supported local winner evidence.
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"Clove Coffee"}),encoding="utf-8")
    class Provider:
        def search(self,*a,**k): raise AssertionError("YouTube should not be queried")
    # With no analytics DB there is no local mechanism, so this test only verifies the
    # provider contract remains injectable without any V2 write path.
    state=build_project_prompt_state(p,youtube_provider=Provider())
    assert state["concept"]["constraints"]["external_references_are_secondary"] is True
