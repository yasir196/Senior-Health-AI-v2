from pathlib import Path
import pytest
from Thumbnail_Pipeline.runner.__main__ import resolve_project

def test_resolves_exact_project_under_projects(tmp_path):
    root=tmp_path/"Projects"; p=root/"my-project"; p.mkdir(parents=True)
    assert resolve_project("my-project",str(root))==p.resolve()

def test_missing_project_fails_clearly(tmp_path):
    root=tmp_path/"Projects"; root.mkdir()
    with pytest.raises(FileNotFoundError):
        resolve_project("missing",str(root))

def test_rejects_path_escape(tmp_path):
    root=tmp_path/"Projects"; root.mkdir()
    with pytest.raises(ValueError):
        resolve_project("../other",str(root))
