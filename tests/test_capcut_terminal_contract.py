import pytest

from capcut_export import (
    CapCutExportError,
    FINAL_MP4_RENDERING_SUPPORTED,
    PIPELINE_TERMINAL_STATE,
    assert_no_final_mp4_request,
    pipeline_terminal_contract,
)


def test_pipeline_terminal_state_is_capcut_ready() -> None:
    assert PIPELINE_TERMINAL_STATE == "CAPCUT_READY"
    assert FINAL_MP4_RENDERING_SUPPORTED is False
    contract = pipeline_terminal_contract()
    assert contract["terminal_state"] == "CAPCUT_READY"
    assert contract["final_mp4_rendering_supported"] is False


def test_final_mp4_request_is_rejected() -> None:
    with pytest.raises(CapCutExportError, match="Final MP4"):
        assert_no_final_mp4_request(render_final_mp4=True)


def test_normal_capcut_handoff_is_allowed() -> None:
    assert_no_final_mp4_request(render_final_mp4=False)
