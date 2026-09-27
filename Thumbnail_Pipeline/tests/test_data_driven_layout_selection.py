from pathlib import Path

from Thumbnail_Pipeline.adapters.v2_analytics_db import V2AnalyticsReadOnlyAdapter
from Thumbnail_Pipeline.runner.__main__ import _layout_family, _select_data_driven_layout


def _winner(title, layout, ctr=6.5, impressions=10000):
    return {
        "title": title,
        "composition_layout": layout,
        "ctr": ctr,
        "impressions": impressions,
    }


def _yt(video_id, layout, views):
    return {
        "video_id": video_id,
        "external_thumbnail_structural_layout": layout,
        "views": views,
    }


def test_db_winner_order_is_used_before_youtube_fallback():
    winners = [
        _winner("winner one", "large text on the left, peanut butter jar on the right"),
        _winner("winner two", "presenter left, large text upper center, feet lower right"),
    ]
    youtube = [
        _yt("yt-second", "text_top_subject_bottom", 900000),
        _yt("yt-first", "text_left_subject_right", 100000),
    ]
    selected = _select_data_driven_layout(winners, youtube)
    assert selected["source"] == "db_winner_validated_on_youtube"
    assert selected["winner_title"] == "winner one"
    assert selected["youtube_match_video_id"] == "yt-first"
    assert selected["layout"] == "text_left_subject_right"
    assert "peanut butter" not in selected["layout"].lower()
    assert "peanut butter" in selected["historical_layout_evidence"].lower()


def test_next_db_winner_is_tried_when_first_layout_is_absent():
    winners = [
        _winner("winner one", "large text on the left, peanut butter jar on the right"),
        _winner("winner two", "presenter left, large text upper center, feet lower right"),
    ]
    youtube = [_yt("yt-second", "text_top_subject_bottom", 500000)]
    selected = _select_data_driven_layout(winners, youtube)
    assert selected["source"] == "db_winner_validated_on_youtube"
    assert selected["winner_title"] == "winner two"


def test_highest_view_youtube_layout_is_fallback_after_all_db_winners_fail():
    winners = [_winner("winner one", "large text on the left, peanut butter jar on the right")]
    youtube = [
        _yt("low", "centered_subject", 10000),
        _yt("high", "subject_left_text_right", 250000),
    ]
    selected = _select_data_driven_layout(winners, youtube)
    assert selected["source"] == "youtube_highest_view_fallback"
    assert selected["youtube_match_video_id"] == "high"
    assert selected["layout"] == "subject_left_text_right"


def test_layout_family_normalizes_db_free_text():
    assert _layout_family("Large text on the left, peanut butter jar on the right") == "text_left_subject_right"
    assert _layout_family("presenter left, large text upper center, feet lower right") == "text_top_subject_bottom"


def test_winner_query_uses_latest_rows_without_summing_snapshots():
    adapter = V2AnalyticsReadOnlyAdapter(Path("unused.db"))
    adapter.latest_thumbnail_evidence = lambda: [
        {"analytics_id": "a", "title": "A", "ctr": 6.2, "impressions": 6000,
         "attribution_status": "post_snapshot_window_observed", "composition_layout": "text left subject right"},
        {"analytics_id": "b", "title": "B", "ctr": 6.9, "impressions": 4999,
         "attribution_status": "post_snapshot_window_observed", "composition_layout": "subject left text right"},
        {"analytics_id": "c", "title": "C", "ctr": 7.0, "impressions": 7000,
         "attribution_status": "historical_thumbnail_version_uncertain", "composition_layout": "centered subject"},
    ]
    winners = adapter.qualifying_thumbnail_layout_winners()
    assert [x["title"] for x in winners] == ["A"]
