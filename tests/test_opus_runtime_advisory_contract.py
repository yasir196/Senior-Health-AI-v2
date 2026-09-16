from pathlib import Path

from app import command_for_stage, writer_runtime_advisory_contract


ROOT = Path(__file__).resolve().parents[1]


def test_generated_opus_package_instruction_uses_advisory_runtime_metadata():
    command = command_for_stage(Path("example-project"), "Prepare Opus Package")

    assert (
        "Runtime: 25 minutes is a soft planning reference "
        "(approximately 4,225 words at 169 WPM)." in command
    )
    assert "Planning runtime reference: 16–35 minutes." in command
    assert "Runtime is ADVISORY ONLY — NON-BLOCKING." in command
    assert "Do not use runtime range, runtime shortfall, runtime overage, word count, or target duration as a PASS/FAIL criterion." in command
    assert "Do not expand, pad, repeat, trim, request additional research, add sources/claims, or route upstream merely to reach a runtime or word-count target." in command
    assert "configured validation range" not in command.lower()
    assert "validation floor" not in command.lower()
    assert "validation boundaries" not in command.lower()


def test_writer_runtime_metadata_is_derived_from_config_not_hardcoded():
    contract = writer_runtime_advisory_contract(
        {
            "target_runtime_minutes": 20,
            "target_runtime_range_minutes": [18, 24],
            "narration_words_per_minute": 150,
        }
    )

    assert "Runtime: 20 minutes" in contract
    assert "approximately 3,000 words at 150 WPM" in contract
    assert "Planning runtime reference: 18–24 minutes" in contract
    assert "4,225" not in contract


def test_writer_template_makes_runtime_report_non_blocking():
    template = (ROOT / "Templates" / "Writing" / "opus_writer_prompt.md").read_text(encoding="utf-8")
    lowered = template.lower()

    assert "Runtime Advisory: ADVISORY ONLY — NON-BLOCKING" in template
    assert "Planning runtime reference" in template
    assert "Use all materially useful approved evidence at legitimate depth" in template
    assert "configured runtime floor" not in lowered
    assert "configured minimum" not in lowered
    assert "validation boundaries" not in lowered
    assert "validation floor" not in lowered
