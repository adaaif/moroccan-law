"""The clock held at a moment that is not on the hour, for the measures' tests."""
import pytest
from django.utils import timezone

from apps.analytics.tests.beacon import MOMENT


@pytest.fixture
def still(monkeypatch):
    """The clock held at MOMENT (14:37:52 UTC, a Saturday of Morocco on Greenwich's time)."""
    monkeypatch.setattr(timezone, 'now', lambda: MOMENT)
    return MOMENT
