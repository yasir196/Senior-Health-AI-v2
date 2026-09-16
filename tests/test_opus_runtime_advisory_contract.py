from pathlib import Path

import pytest

import app
from v31_core import RunResult


ROOT = Path(__file__).resolve().parents[1]


def safe_generated_package() -> str:
    template = (ROOT / "Templates" / "Writing" / "opus_writer_prompt.md").read_text(encoding="utf-8")
    return "# Project Writer Package\n\n" + template


def fake_result() -> RunResult:
    return RunResult(0, "generated", "run.log", "start", "finish", "command")


def test_generator_instruction_contains_no_numeric_runtime_or_word_target():
    command = app.command_for_stage(Path("example-project"), "Prepare Opus Package")
    lowered = command.lower()

    assert "RUNTIME PACKAGE LOCK" in command
    assert "Runtime Advisory: ADVISORY ONLY — NON-BLOCKING" in command
    assert "do not place any automatic runtime target" in lowered
    for stale in ("4,225", "169 wpm", "16-35", "16–35", "configured validation range", "soft planning target"):
        assert stale not in lowered


def test_actual_generated_package_passes_advisory_only_contract(monkeypatch, tmp_path):
    def fake_run(*_args, **_kwargs):
        (tmp_path / "opus_writer_package.md").write_text(safe_generated_package(), encoding="utf-8")
        return fake_result()

    monkeypatch.setattr(app, "run_codex", fake_run)
    result = app.run_external_command("codex", "prompt", tmp_path, stage="Prepare Opus Package")

    assert result.returncode == 0
    assert "Opus Writer package runtime contract: PASS" in result.output
    assert app.opus_writer_package_runtime_issues(tmp_path) == []


@pytest.mark.parametrize(
    "stale_text",
    [
        "The configured validation range is 16-35 minutes.",
        "Use the 16-minute validation floor.",
        "The configured minimum is 16 minutes.",
        "The draft is under the floor.",
        "Runtime: 25 minutes is a soft planning target.",
        "Runtime: 25 minutes is a soft planning reference.",
        "Planning runtime reference: 16–35 minutes.",
        "Aim for 3,700–4,500 words.",
        "Aim for 3,700 to 4,500 words.",
        "Approximately 4,225 words at 169 WPM.",
        "Expand the script because it is short.",
        "Consider additional approved sources/claims to increase length.",
    ],
)
def test_actual_generated_package_blocks_stale_runtime_semantics(monkeypatch, tmp_path, stale_text):
    def fake_run(*_args, **_kwargs):
        package = safe_generated_package() + "\n\n" + stale_text + "\n"
        (tmp_path / "opus_writer_package.md").write_text(package, encoding="utf-8")
        return fake_result()

    monkeypatch.setattr(app, "run_codex", fake_run)
    result = app.run_external_command("codex", "prompt", tmp_path, stage="Prepare Opus Package")

    assert result.returncode == 2
    assert "Opus Writer package runtime contract: FAIL" in result.output
    assert app.opus_writer_package_runtime_issues(tmp_path)


def test_writer_template_preserves_non_runtime_quality_locks():
    template = (ROOT / "Templates" / "Writing" / "opus_writer_prompt.md").read_text(encoding="utf-8")

    assert "## Semantic Progression Lock" in template
    assert "## Retention-First Drafting Lock" in template
    assert "## Execution / No-Negotiation Lock" in template
    assert "Preserve all approved medical meaning and safety caveats" in template
    assert "material-delta test" in template
    assert "Never substitute filler" in template
    assert "Runtime Advisory: ADVISORY ONLY — NON-BLOCKING" in template
