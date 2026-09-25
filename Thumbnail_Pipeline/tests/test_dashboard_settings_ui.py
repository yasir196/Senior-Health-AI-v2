from Thumbnail_Pipeline.dashboard.app import _page

def test_settings_page_contains_editable_controls_and_save_button():
    page=_page().decode("utf-8")
    assert 'name="min_impressions"' in page
    assert 'name="full_reliability_impressions"' in page
    assert "Save Settings" in page
    assert "Source of truth" in page
