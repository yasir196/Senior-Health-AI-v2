from Thumbnail_Pipeline.runner.__main__ import _enforce_numeric_copy_authority


def test_numeric_copy_requires_explicit_count_authority():
    result={"verdict":"PASS","unsupported_slots":[],"reason":"model passed"}
    support={"count_promise":None}
    adaptation={"bottom_callout":"TRY THESE 3"}

    checked=_enforce_numeric_copy_authority(result,support,adaptation)

    assert checked["verdict"]=="FAIL"
    assert checked["unsupported_slots"][0]["slot"]=="bottom_callout"
    assert "3" in checked["unsupported_slots"][0]["reason"]


def test_matching_validated_count_allows_numeric_copy():
    result={"verdict":"PASS","unsupported_slots":[],"reason":"supported"}
    support={"count_promise":{"promised":3,"supported":3,"clearly_identifiable":True}}
    adaptation={"bottom_callout":"TRY THESE 3"}

    checked=_enforce_numeric_copy_authority(result,support,adaptation)

    assert checked==result


def test_mismatched_numeric_copy_is_rejected():
    result={"verdict":"PASS","unsupported_slots":[],"reason":"model passed"}
    support={"count_promise":{"promised":3,"supported":3,"clearly_identifiable":True}}
    adaptation={"bottom_callout":"TRY THESE 4"}

    checked=_enforce_numeric_copy_authority(result,support,adaptation)

    assert checked["verdict"]=="FAIL"
    assert checked["unsupported_slots"][0]["value"]=="TRY THESE 4"
