from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "Templates" / "Writing" / "opus_writer_prompt.md"
APP = ROOT / "app.py"


def test_writer_template_requires_legitimate_depth_without_runtime_padding():
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "## Full Evidence Development Lock" in text
    assert "Do not treat the anti-padding" in text
    assert "Fully develop every materially useful approved evidence module" in text
    assert "Depth is not padding." in text
    assert "what was studied" in text
    assert "what the evidence means" in text
    assert "what it does not mean" in text
    assert "practical viewer consequence" in text
    assert "Do not compress an approved module merely for brevity." in text
    assert "Runtime remains advisory metadata after drafting" in text


def test_prepare_opus_package_preserves_depth_lock_and_gate1_authority():
    text = APP.read_text(encoding="utf-8")

    assert "copy the complete `## Full Evidence Development Lock`" in text
    assert "fully develop every materially useful approved evidence module" in text
    assert "rather than summarize or compress it for brevity" in text
    assert "never reviving unapproved material from research or the outline" in text
    assert "legitimate depth, not padding" in text
    assert "Runtime Advisory: ADVISORY ONLY — NON-BLOCKING" in text



def test_writer_module_completion_is_not_first_correct_coverage():
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "## Full Evidence Development Lock" in text
    assert "Module-completion rule" in text
    assert "NOT complete merely because its claim and boundary have each been stated once" in text
    assert "First correct coverage is the minimum for inclusion, not the completion criterion." in text
    assert "Mandatory pre-finalization evidence-depth completion gate" in text
    assert "`DEVELOP_NOW`" in text
    assert "Finalization prohibition" in text
    assert "zero `DEVELOP_NOW` dimensions remain" in text
    assert "do not remove new interpretation, distinctions, limitations, or consequences" in text
    assert "do not use it to chase a runtime/word-count target" in text


def test_prepare_opus_package_preserves_operational_module_completion_rule():
    text = APP.read_text(encoding="utf-8")

    assert "First correct coverage of a claim plus its boundary is the minimum for inclusion, NOT the completion criterion." in text
    assert "study/population/formulation context" in text
    assert "null/mixed/uncertain-result meaning" in text
    assert "state it once and move on" in text
    assert "mandatory pre-finalization evidence-depth completion gate" in text
    assert "`DEVELOPED`, `DEVELOP_NOW`, or `SKIP_SUPPORTED_REASON`" in text
    assert "zero `DEVELOP_NOW` dimensions remain" in text



def test_writer_depth_gate_cannot_be_satisfied_by_claim_plus_boundary_or_generic_qa():
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "execution gate, not an optional reflection" in text
    assert "A claim plus its boundary being present is never sufficient reason" in text
    assert "are not self-explanatory" in text
    assert "If ANY module has a `DEVELOP_NOW` dimension, the script is NOT complete." in text
    assert "Do not substitute a structural/retention pass, boundary-compliance pass" in text
    assert "do not print it in `06_final_script.md`" in text


def test_prepare_package_requires_module_ledger_not_generic_silent_audit():
    text = APP.read_text(encoding="utf-8")

    assert "silently build a module-by-module completion ledger" in text
    assert "any `DEVELOP_NOW` means the script is NOT complete" in text
    assert "A structural/retention pass or boundary-compliance pass cannot substitute" in text
    assert "must never appear in narration or be used to chase runtime/word count" in text


def test_writer_depth_gate_requires_discrete_exhaustive_matrix_not_module_impression():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Ledger execution protocol — mandatory, discrete pass" in text
    assert "full module × dimension matrix" in text
    assert "all nine dimensions explicitly" in text
    assert "qualifier" in text and "does not qualify" in text
    assert "borderline between `DEVELOPED` and `DEVELOP_NOW`" in text
    assert "rebuild the ENTIRE matrix" in text


def test_prepare_package_preserves_discrete_exhaustive_matrix_protocol():
    text = APP.read_text(encoding="utf-8")
    assert "separate post-draft module × dimension matrix pass" in text
    assert "explicitly disposition all nine dimensions" in text
    assert "qualifier label by itself as NOT developed" in text
    assert "rebuild the ENTIRE matrix" in text
