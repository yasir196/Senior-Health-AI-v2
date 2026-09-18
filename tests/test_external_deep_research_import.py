from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workflow_supports_verbatim_external_deep_research_import():
    text = (ROOT / "app.py").read_text(encoding="utf-8")

    assert '02_external_deep_research.md' in text
    assert 'Save Imported Deep Research' in text
    assert 'Remove Imported Deep Research' in text
    assert 'IMPORTED DEEP RESEARCH mode' in text
    assert 'Do NOT rerun or replace broad topic discovery' in text
    assert 'do not copy the imported report\'s fit verdict blindly' in text
    assert 'shutil.copy2(external_path' in text


def test_research_agent_preserves_import_and_separates_discovery_from_approval():
    text = (ROOT / "Agents" / "Research_Agent.md").read_text(encoding="utf-8")

    assert "## 2A. Imported Deep Research Mode" in text
    assert "Preserve `02_external_deep_research.md` verbatim" in text
    assert "rather than rerunning broad topic discovery" in text
    assert "Verify cited material sources at source level" in text
    assert "Keep `DISCOVERED` evidence conceptually separate from `APPROVED` production claims" in text
    assert "mark it unverified/not production-usable" in text
    assert "Medical_Agent Gate 1 remains the approval authority" in text
    assert "The imported report's own Long-Form Fit verdict" in text
