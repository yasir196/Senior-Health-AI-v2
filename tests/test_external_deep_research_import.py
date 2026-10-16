from pathlib import Path
import app


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


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
    assert "immutable title and independent-research boundary acknowledgment" in text
    assert "immutable title and Stage 1 boundary acknowledgment" not in text


def test_deep_research_handover_keeps_title_but_not_stage1_verdict(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()

    title = "Immutable Test Title"
    stage1_marker = "STAGE1_PRIVATE_VERDICT_MARKER"

    (project / "project.json").write_text(
        f'{{"anchor_title": "{title}"}}',
        encoding="utf-8",
    )
    (project / "01_topic_validation.md").write_text(
        stage1_marker,
        encoding="utf-8",
    )

    package = app.build_deep_research_package(project)

    assert title in package
    assert "## Independent Research Boundary" in package
    assert stage1_marker not in package


def test_imported_source_verification_uses_authoritative_fallbacks_before_unverified():
    text = (ROOT / "Agents" / "Research_Agent.md").read_text(encoding="utf-8")

    assert "Imported-source verification fallback ladder" in text
    assert "a failed or blocked first URL is not, by itself, an unverified source" in text
    assert "PubMed/PMC" in text
    assert "DOI resolution/metadata" in text
    assert "Search by exact title plus author/year" in text
    assert "identity-only" in text
    assert "search-result snippets, AI summaries, blogs, or secondary paraphrases" in text


def test_imported_workflow_command_requires_verification_fallback_ladder():
    text = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "a blocked/dead first URL is not enough to mark a source unverified" in text
    assert "title/author/year/DOI/PMID/PMCID" in text
    assert "full-text/source-level, abstract/metadata-level, or identity-only" in text
