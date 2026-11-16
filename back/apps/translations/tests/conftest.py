import pytest

from apps.sources.services import render


@pytest.fixture(autouse=True)
def upright_pages_put_back():
    """`archive_french` tells the render service, for the rest of its process, that the French pages are upright (no
    orientation asked of Tesseract): put back after each test, so no later test meets it."""
    saved = render._osd_rotation
    yield
    render._osd_rotation = saved
