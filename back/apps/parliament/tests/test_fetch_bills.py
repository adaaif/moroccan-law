"""`fetch_bills`: the Chamber of Representatives' search finds each law's bill page, the page gives the bill as filed
(never the committee's report), and the file is kept under CORPUS_DIR/sources/parliament with its hash, registered by
the law's address. No test reaches the Chamber: a fake network answers in its place."""
import hashlib
import io
import urllib.error
from datetime import date
from urllib.parse import quote_plus

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.corpus.models import Consolidation, Text, Version
from apps.parliament.tests.pdfs import pdf_bytes
from apps.sources.models import Document
from apps.sources.services import fetch

pytestmark = pytest.mark.django_db

SITE = 'https://www.chambredesrepresentants.ma'
LAW = '/akn/ma/act/loi/2026/013-26'
TITLE = 'القانون رقم 013.26 بتغيير وتتميم القانون رقم 2.00 المتعلق بحقوق المؤلف والحقوق المجاورة'
FIRST = f'{SITE}/ar/search?keys={quote_plus("مشروع قانون رقم 013.26")}'
SECOND = f'{SITE}/ar/search?keys={quote_plus("مشروع قانون رقم 013.26 بتغيير وتتميم القانون رقم 2.00 المتعلق")}'
PAGE = f'{SITE}/ar/%D8%A7%D9%84%D9%86%D8%B5%D9%88%D8%B5-%D8%A7%D9%84%D8%AA%D8%B4%D8%B1%D9%8A%D8%B9%D9%8A%D8%A9/mshrw-01326'
RESULTS = (f'<a href="/ar/RapportL1-013.26">تقرير لجنة التعليم حول مشروع قانون رقم 013.26</a>'
           f'<a href="{PAGE.removeprefix(SITE)}">مشروع قانون رقم 013.26 بتغيير وتتميم القانون رقم 2.00</a>').encode()
FILE = f'{SITE}/sites/default/files/loi/Projet_loi_013.26.pdf'
BILL_PAGE = ('<a href="/sites/default/files/loi/Rapport_com_013.26.pdf">التقرير</a>'
             '<a href="/sites/default/files/loi/Projet_loi_013.26.pdf">النص كما أودع</a>').encode()
PDF = pdf_bytes([['مشروع قانون رقم 013.26']], rtl=True)


class Network:
    """The Chamber's site as a dict: url → bytes, an HTTP status, a redirect («→ url») or an error to raise. The opener
    the fetcher builds is this one; a redirect goes through the fetcher's own redirect handler, as urllib's would."""

    def __init__(self):
        self.pages, self.asked, self.handlers = {}, [], []

    def build_opener(self, *handlers):
        self.handlers = handlers
        return self

    def open(self, request, timeout=None):
        url = request.full_url
        self.asked.append(url)
        answer = self.pages.get(url, 404)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, int):
            raise urllib.error.HTTPError(url, answer, 'status', {}, None)
        if isinstance(answer, str):
            handler = next(h for h in self.handlers if hasattr(h, 'redirect_request'))
            return self.open(handler.redirect_request(request, None, 302, 'Found', {}, answer.removeprefix('→ ')))
        return io.BytesIO(answer)


@pytest.fixture
def chamber(monkeypatch, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    fetch._ROBOTS.clear()
    fetch._LAST.clear()
    network = Network()
    network.slept = []
    monkeypatch.setattr(fetch.urllib.request, 'build_opener', network.build_opener)
    monkeypatch.setattr(fetch.time, 'sleep', network.slept.append)
    yield network
    fetch._ROBOTS.clear()
    fetch._LAST.clear()


def law(number='013-26', title=TITLE, uri=LAW, kind='law', in_corpus=True):
    text = Text.objects.create(akn_uri=uri, type=kind, number=number, title_ar=title)
    if in_corpus:
        Version.objects.create(text=text, language='ar', valid_from=date(2026, 8, 10),
                               consolidation=Consolidation.AS_PUBLISHED)
    return text


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    call_command('fetch_bills', *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def bill_document(path='sources/parliament/bill_013.26.pdf', **fields):
    return Document.objects.create(**{
        'source': 'parliament', 'kind': 'parliament', 'sha256': 'b' * 64, 'path': path, 'mime': 'application/pdf',
        'bytes': 1, 'language': 'ar', 'fetched_at': timezone.now(), **fields})


def test_without_fetch_it_names_the_laws_whose_bill_is_not_held_and_asks_nothing(chamber):
    law()
    law('041-25', 'القانون رقم 041.25 بتغيير القانون رقم 39.08', '/akn/ma/act/loi/2025/041-25')
    law('06-26', 'القانون التنظيمي رقم 06.26', '/akn/ma/act/loi-organique/2026/06-26', kind='organic_law')
    law('2-26-1', 'مرسوم رقم 2.26.1', '/akn/ma/act/decret/2026/2-26-1', kind='decree')  # not a law
    law('99-26', 'القانون رقم 99.26', '/akn/ma/act/loi/2026/99-26', in_corpus=False)         # no version: not in the corpus
    bill_document(meta={'text_uri': '/akn/ma/act/loi/2025/041-25'})                       # its bill is held
    said, _ = run()
    assert said.splitlines() == ['   06.26  القانون التنظيمي رقم 06.26', f'  013.26  {TITLE[:70]}',
                                 "2 laws whose bill is not held: --fetch searches the Chamber's site for them"]
    assert run('--only', '013-26')[0].splitlines() == [
        f'  013.26  {TITLE[:70]}', "1 laws whose bill is not held: --fetch searches the Chamber's site for them"]
    assert chamber.asked == []


def test_the_bill_as_filed_is_found_fetched_politely_and_registered_by_its_law(chamber, tmp_path):
    law()
    chamber.pages = {FIRST: RESULTS, PAGE: BILL_PAGE, FILE: PDF}
    said, _ = run('--fetch')
    assert said.splitlines() == [f'  013.26  {FILE}', "1 bills fetched, 0 not found on the Chamber's site"]
    assert chamber.asked == [f'{SITE}/robots.txt', FIRST, PAGE, FILE]
    assert chamber.slept == [2, 2, 2]           # two seconds before each request to the Chamber
    assert (tmp_path / 'sources' / 'parliament' / 'bill_013.26.pdf').read_bytes() == PDF
    doc = Document.objects.get()
    assert (doc.source, doc.kind, doc.language, doc.url, doc.path, doc.page_count) == (
        'parliament', 'parliament', 'ar', FILE, 'sources/parliament/bill_013.26.pdf', 1)
    assert doc.title == 'مشروع قانون رقم 013.26 — النص كما أودع'
    assert doc.meta == {'text_uri': LAW, 'bill': '013.26', 'page': PAGE}
    # Held now: the next run looks for nothing.
    assert run()[0] == "0 laws whose bill is not held: --fetch searches the Chamber's site for them\n"


def test_a_bill_the_search_does_not_give_is_looked_for_three_ways_then_said_missing(chamber, tmp_path):
    law()
    chamber.pages = {FIRST: b'<p>no result</p>', SECOND: RESULTS.replace(b'013.26', b'013.25')}
    said, _ = run('--fetch')
    assert said.splitlines() == ['  013.26  not found', "0 bills fetched, 1 not found on the Chamber's site"]
    assert chamber.asked == [f'{SITE}/robots.txt', FIRST, SECOND, f'{FIRST}&page=1']
    assert not Document.objects.exists() and not any((tmp_path / 'sources' / 'parliament').iterdir())


@pytest.mark.parametrize('pages', [
    {FIRST: RESULTS, PAGE: b'<a href="/sites/default/files/loi/Rapport_com_013.26.pdf">r</a>'},  # the report only
    {FIRST: RESULTS, PAGE: 500},                                                                 # the page fails
    {FIRST: urllib.error.URLError('no route to host')},                                          # the site is down
    {FIRST: RESULTS.replace(PAGE.removeprefix(SITE).encode(), b'https://www.example.org/a/%D8%A7%D9%84%D9%86%D8%B5%D9%88%D8%B5-%D8%A7%D9%84%D8%AA%D8%B4%D8%B1%D9%8A%D8%B9%D9%8A%D8%A9')},
], ids=['only-the-report', 'page-fails', 'site-down', 'result-on-another-host'])
def test_a_page_without_the_bill_or_that_does_not_answer_leaves_the_law_for_later(chamber, pages):
    law()
    chamber.pages = pages
    said, _ = run('--fetch')
    assert said.splitlines()[0] == '  013.26  not found'
    assert not Document.objects.exists()
    assert not any(url.startswith('https://www.example.org/') for url in chamber.asked)


@pytest.mark.parametrize('answer, err', [
    (b'<html>Page introuvable</html>', None),                                     # an error page, not a PDF
    ('→ https://www.example.org/Projet_loi_013.26.pdf', 'https://www.example.org/Projet_loi_013.26.pdf: not an address'),
], ids=['not-a-pdf', 'redirect-to-another-host'])
def test_a_file_that_is_not_the_bills_pdf_is_left_and_the_run_goes_on(chamber, tmp_path, answer, err):
    law()
    law('041-25', 'القانون رقم 041.25 بتغيير القانون رقم 39.08', '/akn/ma/act/loi/2025/041-25')
    other = f'{SITE}/ar/search?keys={quote_plus("مشروع قانون رقم 041.25")}'
    chamber.pages = {FIRST: RESULTS, PAGE: BILL_PAGE, FILE: answer, other: b''}
    said, said_err = run('--fetch')
    assert said.splitlines()[-1] == "0 bills fetched, 2 not found on the Chamber's site"
    assert other in chamber.asked                       # the next law is still looked for
    assert said_err.startswith(err) if err else said_err == ''
    assert not (tmp_path / 'sources' / 'parliament' / 'bill_013.26.pdf').exists() and not Document.objects.exists()


def test_a_refusal_stops_the_run_with_its_reason(chamber):
    law()
    chamber.pages = {f'{SITE}/robots.txt': 403}
    with pytest.raises(CommandError, match=r'refuses its robots\.txt to us'):
        run('--fetch')
    assert chamber.asked == [f'{SITE}/robots.txt']


def test_a_file_kept_before_is_not_fetched_again_and_a_sample_row_gets_its_laws_address(chamber, tmp_path):
    law()
    path = tmp_path / 'sources' / 'parliament' / 'bill_013.26.pdf'
    path.parent.mkdir(parents=True)
    path.write_bytes(PDF)
    sample = bill_document(sha256=hashlib.sha256(PDF).hexdigest(), url='', meta={'sample': True})
    chamber.pages = {FIRST: RESULTS, PAGE: BILL_PAGE}
    said, _ = run('--fetch')
    assert said.splitlines()[0] == f'  013.26  {FILE}'
    assert FILE not in chamber.asked
    sample.refresh_from_db()
    assert sample.meta == {'sample': True, 'text_uri': LAW, 'bill': '013.26', 'page': PAGE} and sample.url == FILE
    assert Document.objects.count() == 1
