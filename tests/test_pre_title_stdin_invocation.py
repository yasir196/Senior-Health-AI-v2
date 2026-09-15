from pathlib import Path


def test_pre_title_uses_stdin_prompt_sentinel():
    source = Path('app.py').read_text(encoding='utf-8')
    start = source.index('def _run_pre_title_check')
    end = source.index('def _render_pre_title_result', start)
    block = source[start:end]
    assert 'template.replace("{prompt}", "-")' in block
    assert 'input=prompt' in block
    assert 'quoted = shlex.quote(prompt)' not in block


def test_pre_title_remains_read_only_and_nonpersistent():
    source = Path('app.py').read_text(encoding='utf-8')
    start = source.index('def _run_pre_title_check')
    end = source.index('def _render_pre_title_result', start)
    block = source[start:end]
    assert 'replace("--sandbox workspace-write", "--sandbox read-only")' in block
    assert 'save_json(' not in block
    assert 'write_text(' not in block
