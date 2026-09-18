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


def test_deep_research_handover_package_is_available_from_research_stage():
    text = APP.read_text(encoding="utf-8")

    assert "def build_deep_research_package" in text
    assert "Prepare Deep Research Package" in text
    assert "opus_research_package.md" in text
    assert "Download Deep Research Package" in text
    assert "Be conservative about CLAIM STRENGTH, not about SEARCH BREADTH." in text
    assert "Prefer senior-specific or older-adult evidence when available" in text
    assert "positive, null/mixed/negative, counterevidence, and safety findings" in text
    assert "semantic-saturation note" in text
    assert "LONG-FORM FIT: SUPPORTED" in text
    assert "LONG-FORM FIT: NOT RECOMMENDED" in text
    assert "Medical Gate 1 remains the authority for approved narration claims" in text


def test_deep_research_handover_embeds_stage1_and_immutable_title():
    text = APP.read_text(encoding="utf-8")

    assert 'resolve_title_anchor(project)' in text
    assert 'safe_read_text(project / "01_topic_validation.md")' in text
    assert "Do not rewrite, repair, replace, rank, or re-adjudicate the title." in text
    assert "Return one complete research report suitable for direct paste" in text
