import io
import time
import urllib.error

import pytest


class Site:
    """The government's sites as a dict: url → bytes, an HTTP status, an exception to raise, or a function of the
    request's headers giving one of those. The opener the fetchers build is this one."""

    def __init__(self):
        self.pages, self.asked, self.slept = {}, [], []

    def open(self, request, timeout=None):
        url, headers = request.full_url, dict(request.header_items())
        self.asked.append(url)
        answer = self.pages.get(url, 404)
        if callable(answer):
            answer = answer(headers)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, int):
            raise urllib.error.HTTPError(url, answer, 'Not Found' if answer == 404 else 'Error', {}, None)
        return io.BytesIO(answer)


@pytest.fixture
def sgg(monkeypatch, settings, tmp_path):
    """No fetcher reaches a real site: the SGG, Adala and the others answer from `pages`; robots.txt is absent (404, so
    everything is allowed) unless a test gives one; the pauses between files are counted, never waited."""
    from apps.sources.services import fetch

    settings.CORPUS_DIR = tmp_path
    fetch._ROBOTS.clear()
    fetch._LAST.clear()
    site = Site()
    monkeypatch.setattr(fetch.urllib.request, 'build_opener', lambda *handlers: site)
    monkeypatch.setattr(fetch.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('a fetcher reached for the network'))
    monkeypatch.setattr(time, 'sleep', site.slept.append)
    yield site
    fetch._ROBOTS.clear()
    fetch._LAST.clear()
