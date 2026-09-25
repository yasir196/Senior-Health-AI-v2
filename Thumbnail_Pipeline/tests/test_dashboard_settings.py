import json
from pathlib import Path
import pytest
from Thumbnail_Pipeline.dashboard import settings as dashboard_settings

def test_dashboard_settings_validation():
    with pytest.raises(ValueError):
        dashboard_settings.save_dashboard_settings(min_impressions=1000,full_reliability_impressions=999)

def test_editable_setting_names_are_explicit():
    assert dashboard_settings.EDITABLE_SETTINGS==("eligibility.min_impressions","reliability.full_reliability_impressions")
