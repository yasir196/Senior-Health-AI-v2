from Thumbnail_Pipeline.runner.__main__ import _enforce_optional_text_band_authority


def _metadata(*, required=False):
    band = {"band_id": "band_4"}
    if required:
        band["required"] = True
    return {"structural_contract": {"bands": [band]}}


def test_historical_cta_prose_cannot_require_optional_bottom_callout():
    result = {
        "verdict": "FAIL",
        "findings": [{
            "area": "text_flow/cta_missing",
            "reason": "Historical progressive_hook_then_cta says the CTA band must remain visually distinct; bottom_callout is omitted.",
        }],
        "reason": "CTA missing",
    }
    out = _enforce_optional_text_band_authority(result, _metadata())
    assert out["verdict"] == "PASS"
    assert out["findings"] == []


def test_valid_non_cta_finding_survives_optional_band_filter():
    result = {
        "verdict": "FAIL",
        "findings": [
            {
                "area": "text_flow / CTA band missing",
                "reason": "Historical CTA is required and bottom_callout is null.",
            },
            {
                "area": "boxed_keyword duplicates headline timing info",
                "reason": "AT NIGHT repeats NIGHTTIME and should be removed.",
            },
        ],
        "reason": "two defects",
    }
    out = _enforce_optional_text_band_authority(result, _metadata())
    assert out["verdict"] == "FAIL"
    assert len(out["findings"]) == 1
    assert "duplicates" in out["findings"][0]["area"]


def test_explicit_machine_readable_required_true_preserves_cta_finding():
    result = {
        "verdict": "FAIL",
        "findings": [{
            "area": "CTA missing",
            "reason": "Required CTA is omitted.",
        }],
        "reason": "required band missing",
    }
    out = _enforce_optional_text_band_authority(result, _metadata(required=True))
    assert out == result
