from pathlib import Path
import opus_image_prompt_import as mod

def test_backup_filename_is_short_and_folder_created(tmp_path: Path):
    project = tmp_path / ("p" * 80)
    project.mkdir(parents=True)
    source = project / "10_image_prompts.md"
    source.write_text("old prompts", encoding="utf-8")

    backup = mod.backup_existing_prompt_file(project)

    assert backup is not None and backup.is_file()
    assert backup.parent.name == "Backups"
    assert backup.name.startswith("10_img_")
    assert len(backup.name) < 40
    assert backup.read_text(encoding="utf-8") == "old prompts"


def test_normal_safe_write(tmp_path: Path):
    path = tmp_path / "10_image_prompts.md"
    mod._write_text_path_safe(path, "a\nb\n")
    assert path.read_text(encoding="utf-8") == "a\nb\n"
