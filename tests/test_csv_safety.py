import csv
from pathlib import Path

import pytest

from avatar_timing import load_production_scenes
from csv_safety import (
    SPREADSHEET_ERROR_VALUES,
    protect_spreadsheet_text,
    recover_spreadsheet_text,
    recover_utf8_mojibake,
    sanitize_csv_file,
    validate_script_text,
)
from timeline_builder import TimelineBuildError, build_timeline_manifest


@pytest.mark.parametrize("text", ["=- text", "+ text", "- text", "@ text"])
def test_formula_like_text_round_trips_without_visible_change(text):
    protected = protect_spreadsheet_text(text)
    assert protected == "'" + text
    assert recover_spreadsheet_text(protected) == text


def test_normal_narration_is_unchanged():
    text = "Normal narration"
    assert protect_spreadsheet_text(text) == text
    assert recover_spreadsheet_text(text) == text


@pytest.mark.parametrize("error", sorted(SPREADSHEET_ERROR_VALUES))
def test_all_spreadsheet_errors_are_rejected(error):
    with pytest.raises(ValueError) as exc:
        validate_script_text(error, "S064")
    assert str(exc.value) == f"Scene S064 contains spreadsheet-corrupted script text: {error}"


def test_production_sheet_reader_recovers_protective_quote(tmp_path: Path):
    sheet = tmp_path / "07_production_sheet.csv"
    with sheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scene_id", "script_excerpt"])
        writer.writeheader()
        writer.writerow({"scene_id": "S064", "script_excerpt": "'=- about olive oil"})
    assert load_production_scenes(sheet)[0]["script_text"] == "=- about olive oil"


def test_production_sheet_reader_rejects_corrupted_text(tmp_path: Path):
    sheet = tmp_path / "07_production_sheet.csv"
    with sheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scene_id", "script_excerpt"])
        writer.writeheader()
        writer.writerow({"scene_id": "S064", "script_excerpt": "#NAME?"})
    with pytest.raises(ValueError, match=r"Scene S064 contains spreadsheet-corrupted script text: #NAME\?"):
        load_production_scenes(sheet)


def test_timeline_reader_recovers_quote_and_rejects_errors(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    path = project / "08_actual_timeline.csv"
    fields = ["Scene ID", "Script Text", "Actual Audio Start", "Actual Audio End", "Duration", "Avatar Chunk", "Timing Source"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"Scene ID":"S064","Script Text":"'=@ text","Actual Audio Start":"00:00.0","Actual Audio End":"00:04.5","Duration":"4.48","Avatar Chunk":"c1.mp4","Timing Source":"TRANSCRIPT"})
    result = build_timeline_manifest(project)
    import json
    data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert data["scenes"][0]["narration_text"] == "=@ text"

    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    rows[0]["Script Text"] = "#VALUE!"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    with pytest.raises(TimelineBuildError, match=r"Scene S064 contains spreadsheet-corrupted script text: #VALUE!"):
        build_timeline_manifest(project)



@pytest.mark.parametrize(
    ("corrupted", "expected"),
    [
        ("tell usâ€”not proof", "tell us—not proof"),
        ("seniorâ€™s choice", "senior’s choice"),
        ("item â€¢ item", "item • item"),
        ("â‰ˆ20 minutes", "≈20 minutes"),
    ],
)
def test_recover_utf8_mojibake_repairs_common_production_punctuation(corrupted, expected):
    assert recover_utf8_mojibake(corrupted) == expected


def test_recover_utf8_mojibake_leaves_normal_unicode_unchanged():
    text = "Normal — senior’s “voice” • approximately ≈20 minutes"
    assert recover_utf8_mojibake(text) == text


def test_production_csv_sanitizer_repairs_mojibake_and_preserves_utf8(tmp_path: Path):
    sheet = tmp_path / "07_production_sheet.csv"
    original = "It is a boundary on what the study can tell usâ€”not proof of a raw-onion brain benefit."
    with sheet.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scene_id", "script_excerpt"])
        writer.writeheader()
        writer.writerow({"scene_id": "SC055", "script_excerpt": original})

    sanitize_csv_file(sheet, required_text_columns=("script_excerpt",))

    with sheet.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["script_excerpt"] == "It is a boundary on what the study can tell us—not proof of a raw-onion brain benefit."
    assert "â€”" not in sheet.read_text(encoding="utf-8-sig")


def test_avatar_production_reader_repairs_mojibake_defensively(tmp_path: Path):
    sheet = tmp_path / "07_production_sheet.csv"
    with sheet.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["scene_id", "script_excerpt"])
        writer.writeheader()
        writer.writerow({"scene_id": "SC055", "script_excerpt": "tell usâ€”not proof"})
    assert load_production_scenes(sheet)[0]["script_text"] == "tell us—not proof"



def test_cp1252_production_csv_is_read_and_sanitized_to_utf8(tmp_path: Path):
    sheet = tmp_path / "07_production_sheet.csv"
    # 0x97 is a Windows-1252 em dash and is invalid as standalone UTF-8.
    sheet.write_bytes(
        b"scene_id,script_excerpt\r\n"
        b'SC074,"This is a legacy cp1252 dash \x97 not UTF-8."\r\n'
    )

    rows = load_production_scenes(sheet)
    assert rows[0]["script_text"] == "This is a legacy cp1252 dash — not UTF-8."

    sanitize_csv_file(sheet, required_text_columns=("script_excerpt",))
    text = sheet.read_text(encoding="utf-8-sig")
    assert "legacy cp1252 dash — not UTF-8" in text
