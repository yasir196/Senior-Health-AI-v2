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
