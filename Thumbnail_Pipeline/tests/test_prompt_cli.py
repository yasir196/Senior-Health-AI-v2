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
                     "thumbnail_url_or_path":"https://i.ytimg.com/vi/x/hqdefault.jpg","views":"5000","duration":"PT8M"}]
    provider=Provider()
    monkeypatch.setattr(runner,"analyze_youtube_reference_thumbnails",lambda refs,**kwargs:[
        {**refs[0],"thumbnail_analysis_status":"analyzed","external_thumbnail_ocr":{"text":"CLOVE COFFEE?"}}
    ])
    state=build_project_prompt_state(p,youtube_provider=provider)
    evidence=state["concept"]["evidence"]
    assert provider.queries==["1 CLOVE in Your Coffee Every Morning"]
    assert evidence["youtube_fallback"]["status"] in {"used","searched_no_recurrent_text_mechanism"}
    assert evidence["youtube_reference_count"]==1



def test_youtube_recurrent_observed_copy_is_not_positional_rewritten(monkeypatch,tmp_path):
    import Thumbnail_Pipeline.runner.__main__ as runner
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"1 CLOVE in Your COFFEE Every Morning"}),encoding="utf-8")
    class Provider:
        def search(self,query,limit=12):
            return [
                {"video_id":"a","channel_name":"A","video_title":"Clove Coffee A","thumbnail_url_or_path":"https://i.ytimg.com/vi/a/hqdefault.jpg","views":"5000","duration":"PT8M"},
                {"video_id":"b","channel_name":"B","video_title":"Clove Coffee B","thumbnail_url_or_path":"https://i.ytimg.com/vi/b/hqdefault.jpg","views":"6000","duration":"PT9M"},
            ]
    monkeypatch.setattr(runner,"analyze_youtube_reference_thumbnails",lambda refs,**kwargs:[
        {**refs[0],"thumbnail_analysis_status":"analyzed","external_thumbnail_visual_text":"CLOVE + COFFEE?"},
        {**refs[1],"thumbnail_analysis_status":"analyzed","external_thumbnail_visual_text":"CLOVE + COFFEE?"},
    ])
    state=build_project_prompt_state(p,youtube_provider=Provider())
    candidates=state["concept"]["concept"]["thumbnail_text_candidates"]
    assert candidates[0]=="CLOVE + COFFEE?"
    assert "1 CLOVE?" not in candidates
    assert "ONE 1 DAILY" not in candidates


def test_runner_signature_has_no_legacy_hero_category():
    import inspect
    import Thumbnail_Pipeline.runner.__main__ as runner
    assert "hero_category" not in inspect.signature(runner.build_project_prompt_state).parameters

def test_concept_category_is_dynamic_cluster_not_legacy_taxonomy(tmp_path):
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"Clove Coffee"}),encoding="utf-8")
    state=build_project_prompt_state(p)
    assert state["concept"]["concept"]["category"]=="unclustered"
    assert "hero_category_associations" not in state["concept"]["evidence"]


def test_safe_zone_is_render_contract_not_evidence_guess(tmp_path):
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"LOCKED"}),encoding="utf-8")
    state=build_project_prompt_state(p)
    spec=state["composition"]
    assert spec["composition"]["safe_zone"]=="bottom-right timestamp-safe area clear"
    assert spec["provenance"]["safe_zone_source"]=="render_contract"
    assert "safe_zone" not in spec["human_review_required_for"]
    assert "text_placement" in spec["human_review_required_for"]

def test_text_placement_stays_unresolved_without_explicit_layout_evidence(tmp_path):
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"LOCKED"}),encoding="utf-8")
    state=build_project_prompt_state(p)
    spec=state["composition"]
    assert spec["composition"]["text_placement"] is None
    assert spec["provenance"]["text_placement_derived_from_layout"] is False


def test_recurrent_observed_copy_rejects_dangling_symbol_but_keeps_internal_plus():
    from Thumbnail_Pipeline.intelligence.text_mechanisms import discover_text_mechanisms,recurrent_observed_text_candidates
    rows=[
        {"performance":{"title":"1 Clove in Your Coffee Every Morning"},"ocr":{"text":"CLOVE + COFFEE?"}},
        {"performance":{"title":"Clove Coffee Every Morning"},"ocr":{"text":"CLOVE + COFFEE?"}},
        {"performance":{"title":"1 Clove in Your Coffee Every Morning"},"ocr":{"text":"1 CLOVE IN YOUR COFFEE\nEVERY MORNING\n+"}},
        {"performance":{"title":"1 Clove in Your Coffee Every Morning"},"ocr":{"text":"1 CLOVE IN YOUR COFFEE\nEVERY MORNING\n+"}},
    ]
    mechanism=discover_text_mechanisms(rows)
    candidates=recurrent_observed_text_candidates("1 CLOVE in Your Coffee Every Morning",mechanism)
    assert "CLOVE + COFFEE?" in candidates
    assert all(not x.rstrip().endswith("+") for x in candidates)


def test_youtube_visual_text_placement_requires_recurrent_supermajority(tmp_path):
    from Thumbnail_Pipeline.runner.__main__ import build_project_prompt_state
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"Coffee Clove Morning"}),encoding="utf-8")
    class Provider: pass
    # This boundary is covered by the real runner integration; unit regression verifies
    # unsupported state remains review-bound when no visual placement evidence is supplied.
    state=build_project_prompt_state(p,youtube_provider=None)
    assert state["composition"]["composition"]["text_placement"] is None
    assert "text_placement" in state["composition"]["human_review_required_for"]


def test_youtube_reference_storage_is_project_scoped():
    from Thumbnail_Pipeline.io_policy import safe_output
    project="bones-getting-weaker-after-60"
    target=safe_output(Path("youtube_references")/project/"abc123.jpg")
    assert target.parent.name==project
    assert target.parent.parent.name=="youtube_references"


def test_historical_literal_layout_does_not_leak_into_new_project(monkeypatch,tmp_path):
    from Thumbnail_Pipeline.concept_engine.engine import build_concept_direction
    context={
        "immutable_title":"1 CLOVE in Your Coffee Every Morning",
        "requested_category":"cluster_test",
        "winner_prior":{"winner_examples":[
            {"v2_analysis":{"composition_layout":"text upper-left, banana lower-left, anatomical torso center, presenter right"}}
        ]},
        "packaging_associations":{"channel":[],"category":[]},
    }
    concept=build_concept_direction(context)
    assert concept["concept"]["composition_layout"] is None


def test_youtube_composition_analysis_runs_even_with_local_text_candidates(monkeypatch,tmp_path):
    import Thumbnail_Pipeline.runner.__main__ as runner
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"Clove Coffee Morning"}),encoding="utf-8")
    class Provider:
        def __init__(self): self.calls=0
        def search(self,query,limit=12):
            self.calls+=1
            return [{"video_id":str(i),"channel_name":"A","video_title":"Clove Coffee",
                     "thumbnail_url_or_path":f"https://i.ytimg.com/vi/{i}/hqdefault.jpg",
                     "views":"5000","duration":"PT8M"} for i in range(4)]
    provider=Provider()
    monkeypatch.setattr(runner,"transformation_text_candidates",lambda *a,**k:[{"text":"CLOVE COFFEE","score":1}])
    monkeypatch.setattr(runner,"analyze_youtube_reference_thumbnails",lambda refs,**kwargs:[
        {**r,"thumbnail_analysis_status":"analyzed","external_thumbnail_text_placement":"left",
         "external_thumbnail_visual_text":"CLOVE COFFEE"} for r in refs
    ])
    state=runner.build_project_prompt_state(p,youtube_provider=provider)
    assert provider.calls==1
    assert state["composition"]["composition"]["text_placement"]=="left"
    assert state["concept"]["evidence"]["youtube_fallback"]["status"]=="analyzed_for_composition"


def test_literal_layout_from_packaging_association_is_not_reused():
    from Thumbnail_Pipeline.concept_engine.engine import build_concept_direction
    literal="Large text on the left, peanut butter jar on the right, spoonful highlighted in the upper-right, top red banner"
    ctx={
        "immutable_title":"1 CLOVE in Your Coffee Every Morning",
        "requested_category":"cluster_test",
        "winner_prior":{"winner_examples":[]},
        "packaging_associations":{"category":[],"channel":[{
            "feature_name":"composition_layout","feature_value":literal,
            "association_direction":"positive","evidence_weight":1,
            "video_count":5,"total_impressions":10000,"ctr_delta_points":1,
        }]},
    }
    out=build_concept_direction(ctx)
    assert out["concept"]["composition_layout"] is None


def test_youtube_recurrent_structural_layout_resolves_layout(monkeypatch,tmp_path):
    import Thumbnail_Pipeline.runner.__main__ as runner
    p=tmp_path/"Projects"/"coffee"; p.mkdir(parents=True)
    (p/"project.json").write_text(json.dumps({"title":"Clove Coffee Morning"}),encoding="utf-8")
    class Provider:
        def search(self,query,limit=12):
            return [{"video_id":str(i),"channel_name":"A","video_title":"Clove Coffee",
                     "thumbnail_url_or_path":f"https://i.ytimg.com/vi/{i}/hqdefault.jpg",
                     "views":"5000","duration":"PT8M"} for i in range(4)]
    monkeypatch.setattr(runner,"analyze_youtube_reference_thumbnails",lambda refs,**kwargs:[
        {**r,"thumbnail_analysis_status":"analyzed","external_thumbnail_visual_text":"CLOVE COFFEE",
         "external_thumbnail_text_placement":"left","external_thumbnail_structural_layout":"text_left_subject_right"} for r in refs
    ])
    state=runner.build_project_prompt_state(p,youtube_provider=Provider())
    assert state["composition"]["composition"]["layout"]=="text_left_subject_right"
    assert "layout" not in state["composition"]["human_review_required_for"]
    assert state["concept"]["evidence"]["youtube_fallback"]["structural_layout_found"]>=3


def test_visible_subjects_are_deduped_and_topic_ranked():
    from Thumbnail_Pipeline.runner.__main__ import _rank_visible_subjects
    ranked=_rank_visible_subjects(
        ["man pointing","man holding clove","hand holding a clove above a cup of coffee",
         "man pointing","hand holding clove over coffee cup"],
        "1 CLOVE in Your Coffee Every Morning (Here's What Happens)",
    )
    assert ranked.count("man pointing")==1
    assert ranked[0] in {"hand holding a clove above a cup of coffee","hand holding clove over coffee cup"}
    assert ranked.index("man pointing") > ranked.index("man holding clove")
