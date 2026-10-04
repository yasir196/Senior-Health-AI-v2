from Thumbnail_Pipeline.adapters.winner_metadata import _sanitize_topic_adaptation


def _sanitize(adapted):
    return _sanitize_topic_adaptation(
        adapted,
        immutable_title="Over 60? Why Your Magnesium Isn't Working (3 Nighttime Mistakes)",
        selected_text="3 NIGHTTIME MISTAKES",
    )


def test_deterministic_dedup_collapses_later_night_substring():
    out=_sanitize({
        "top_banner":"MAGNESIUM",
        "primary_headline":"3 NIGHTTIME MISTAKES",
        "boxed_keyword":"AT NIGHT",
        "bottom_callout":None,
    })
    assert out["primary_headline"]=="3 NIGHTTIME MISTAKES"
    assert out["boxed_keyword"] is None


def test_deterministic_dedup_collapses_later_exact_subject():
    out=_sanitize({
        "top_banner":"MAGNESIUM",
        "primary_headline":"3 NIGHTTIME MISTAKES",
        "boxed_keyword":"MAGNESIUM",
        "bottom_callout":None,
    })
    assert out["top_banner"]=="MAGNESIUM"
    assert out["boxed_keyword"] is None


def test_deterministic_dedup_never_deletes_immutable_copy():
    out=_sanitize({
        "top_banner":"NIGHTTIME",
        "primary_headline":"3 NIGHTTIME MISTAKES",
        "boxed_keyword":None,
        "bottom_callout":None,
    })
    assert out["primary_headline"]=="3 NIGHTTIME MISTAKES"
    assert sum(
        str(out.get(k) or "").casefold()=="3 nighttime mistakes"
        for k in ("top_banner","primary_headline","boxed_keyword","bottom_callout")
    )==1


def test_deterministic_dedup_preserves_distinct_useful_qualifier():
    out=_sanitize({
        "top_banner":"MAGNESIUM",
        "primary_headline":"3 NIGHTTIME MISTAKES",
        "boxed_keyword":"MEDICINE TIMING",
        "bottom_callout":None,
    })
    assert out["boxed_keyword"]=="MEDICINE TIMING"


def test_deterministic_dedup_is_topic_independent_for_containment():
    out=_sanitize({
        "top_banner":"BETTER CIRCULATION",
        "primary_headline":"3 NIGHTTIME MISTAKES",
        "boxed_keyword":"CIRCULATION",
        "bottom_callout":None,
    })
    assert out["top_banner"]=="BETTER CIRCULATION"
    assert out["boxed_keyword"] is None


def test_deterministic_dedup_does_not_collapse_unrelated_long_tokens():
    out=_sanitize({
        "top_banner":"BETTER BALANCE",
        "primary_headline":"3 NIGHTTIME MISTAKES",
        "boxed_keyword":"LEG STRENGTH",
        "bottom_callout":None,
    })
    assert out["top_banner"]=="BETTER BALANCE"
    assert out["boxed_keyword"]=="LEG STRENGTH"
