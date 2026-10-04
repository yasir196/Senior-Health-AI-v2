from Thumbnail_Pipeline.runner.__main__ import _thumbnail_copy_psychology


def test_psychology_contract_is_wired_before_script_support():
    import inspect
    from Thumbnail_Pipeline.runner import __main__ as runner

    source=inspect.getsource(runner.main)
    assert source.index("_thumbnail_copy_psychology(") < source.index("_script_support_contract(")
    assert 'selected_text=str(psychology["selected_text"]).strip()' in source


def test_manual_thumbnail_text_bypasses_psychology_selection():
    import inspect
    from Thumbnail_Pipeline.runner import __main__ as runner

    source=inspect.getsource(runner.main)
    assert "selected_text=args.thumbnail_text" in source
    assert "if selected_text is None and script_text and args.vision_api_key:" in source


def test_psychology_contract_has_six_candidate_formula():
    import inspect

    source=inspect.getsource(_thumbnail_copy_psychology)
    assert "exactly six hooks" in source
    assert "two curiosity_gap, two identity_validation, and two stakes" in source
    assert "3 to 5 whitespace-separated words" in source
    assert "Thumbnail copy must NOT summarize, paraphrase, or mechanically repeat the title" in source
    assert "Curiosity must be a true gap the video actually closes" in source
    assert "5th-6th grade reading level" in source
    assert "TWO-SECOND TEST" in source
    assert "simpler script-supported phrase" in source
