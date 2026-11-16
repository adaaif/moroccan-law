"""The law's words that leave by other doors than a text's own count against the day of reading (OP17 of the
open-source audit): a printed page's image (one article, as its reading counts), a source file whole (each of its
pages), a card to forward that carries an article, and a link's picture of an article. Each is the reader's browser's
to keep, never a shared cache's; an address that leads nowhere, a text's own picture and an answer's card count
nothing."""
import hashlib

import pypdfium2 as pdfium
import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from apps.corpus.tests.test_reading_budget import counted
from apps.discussion.tests.conftest import ARTICLE, lease, uploads  # noqa: F401  (fixtures)
from apps.sources.models import Document, Issue, Page

pytestmark = pytest.mark.django_db
READER = {'HTTP_CF_CONNECTING_IP': '105.155.1.2', 'HTTP_X_FORWARDED_FOR': '105.155.1.2, 127.0.0.1'}


@pytest.fixture(autouse=True)
def fresh(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def issue(lease, tmp_path):
    pdf = pdfium.PdfDocument.new()
    for _ in range(2):
        pdf.new_page(595, 842)
    (tmp_path / 'issues').mkdir()
    pdf.save(str(tmp_path / 'issues' / 'BO_6208_ar.pdf'))
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=hashlib.sha256(b'6208').hexdigest(),
                                  path='issues/BO_6208_ar.pdf', mime='application/pdf', language='ar', bytes=1,
                                  page_count=2, fetched_at=timezone.now())
    Issue.objects.filter(number=6208).update(document=doc)
    for i in range(2):
        Page.objects.create(document=doc, index=i, kind='text_layer', text='نص', text_source='layer')
    return doc


def _drained(r):
    if hasattr(r, 'streaming_content'):
        b''.join(r.streaming_content)
    return r


DOORS = {
    'image': lambda doc: (f'/api/sources/documents/{doc.pk}/pages/0/image/', {'w': '900'}, 1),
    'file': lambda doc: (f'/api/sources/documents/{doc.pk}/file/', {}, 2),
    'share': lambda doc: ('/api/explain/card/', {'path': ARTICLE}, 1),
}


@override_settings(READING_BUDGET=2)
@pytest.mark.parametrize('door', [pytest.param(d, marks=pytest.mark.needs('fribidi')) if d == 'share' else d for d in DOORS])
def test_a_side_door_counts_what_it_gives(api, issue, door):
    url, asked, given = DOORS[door](issue)
    first = _drained(api.get(url, asked, **READER))
    assert first.status_code == 200 and counted() == given
    assert first['Cache-Control'].startswith('private')               # a shared cache would hand it on uncounted
    if given == 1:
        again = _drained(api.get(url, asked, **READER))
        assert again.status_code == 200 and again['Cache-Control'].startswith('private')
    past = api.get(url, asked, **READER)
    assert past.status_code == 429 and past.json() == {'errors': [{'field': 'reading', 'code': 'limit'}]}


@override_settings(READING_BUDGET=1)
@pytest.mark.needs('fribidi')
def test_what_gives_no_article_counts_nothing(api, issue):
    assert api.get(f'/api/sources/documents/{issue.pk}/pages/9/image/', **READER).status_code == 404
    assert api.get('/api/corpus/card/', {'path': '/ma/loi/2013/67-12/art_99'}, **READER).status_code == 404
    assert api.get('/api/explain/card/', {'path': '/ma/loi/2013/67-12/art_99'}, **READER).status_code == 404
    text = _drained(api.get('/api/corpus/card/', {'path': '/ma/loi/2013/67-12'}, **READER))   # its name alone
    assert text.status_code == 200 and text['Cache-Control'] == 'public, max-age=86400'
    assert counted() == 0
    shared = _drained(api.get('/api/explain/card/', {'path': '/ma/loi/2013/67-12'}, **READER))
    assert shared.status_code == 200 and counted() == 0
    # A link's picture of an article, four lines for a preview, counts nothing either.
    link = _drained(api.get('/api/corpus/card/', {'path': ARTICLE}, **READER))
    assert link.status_code == 200 and link['Cache-Control'] == 'public, max-age=86400'
    assert counted() == 0
    # The day is whole: one article left.
    assert _drained(api.get(f'/api/sources/documents/{issue.pk}/pages/1/image/', {'w': '900'}, **READER)).status_code == 200
    assert api.get(f'/api/sources/documents/{issue.pk}/pages/0/image/', {'w': '900'}, **READER).status_code == 429


@override_settings(READING_BUDGET=1)
@pytest.mark.needs('fribidi')
def test_a_reader_past_the_day_is_drawn_nothing(api, issue, tmp_path):
    assert _drained(api.get('/api/explain/card/', {'path': ARTICLE}, **READER)).status_code == 200
    drawn = set((tmp_path / 'cards').rglob('*'))
    assert api.get('/api/explain/card/', {'path': ARTICLE}, **READER).status_code == 429
    assert api.get(f'/api/sources/documents/{issue.pk}/pages/0/image/', **READER).status_code == 429
    assert set((tmp_path / 'cards').rglob('*')) == drawn and not (tmp_path / 'drawn').exists()
