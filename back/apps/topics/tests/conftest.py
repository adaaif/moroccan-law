import pytest

from apps.topics.services import kit


@pytest.fixture(autouse=True)
def fresh_kit():
    """Each test reads the folders and the checks afresh after it: a check a test recorded goes with its database."""
    yield
    kit.load.cache_clear()
