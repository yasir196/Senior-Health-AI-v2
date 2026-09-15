from pathlib import Path
from v31_core import clean_production_script

def cfg():
    return {"host_name": "Adrian Westbrook"}

def test_visual_cue_only_host_is_not_required_in_voice(tmp_path: Path):
    (tmp_path/"06_final_script.md").write_text(
        "# Conclusion\n"
        "If you value calm guidance, consider subscribing to Evidence After 60.\n\n"
        "[Visual Cue: Adrian Westbrook on camera for a calm close.]\n",
        encoding="utf-8",
    )
    (tmp_path/"06a_voice_script.md").write_text(
        "If you value calm guidance, consider subscribing to Evidence After 60.\n",
        encoding="utf-8",
    )
    result = clean_production_script(tmp_path, cfg())
    assert result.success, result.issues

def test_spoken_host_still_required(tmp_path: Path):
    (tmp_path/"06_final_script.md").write_text(
        "# Hook\nI am Adrian Westbrook, your Health Educator. Welcome.\n",
        encoding="utf-8",
    )
    (tmp_path/"06a_voice_script.md").write_text("Welcome.\n", encoding="utf-8")
    result = clean_production_script(tmp_path, cfg())
    assert not result.success
    assert any("Host identity" in x and "spoken narration" in x for x in result.issues)

def test_host_in_heading_does_not_create_requirement(tmp_path: Path):
    (tmp_path/"06_final_script.md").write_text(
        "# Adrian Westbrook Closing\nThanks for watching and subscribe for more.\n",
        encoding="utf-8",
    )
    (tmp_path/"06a_voice_script.md").write_text(
        "Thanks for watching and subscribe for more.\n", encoding="utf-8"
    )
    result = clean_production_script(tmp_path, cfg())
    assert result.success, result.issues
