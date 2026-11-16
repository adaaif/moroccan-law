"""`watch_finance_bill`: where the year's finance bill stands, from the Chamber of Representatives' feed of bills and its
dossier of the bill (its agenda, its files), the files kept once under CORPUS_DIR with a MANIFEST line and the dossier
page whenever it changes; with --press, the outlets' articles about the bill the press page does not hold yet. No test
reaches a site: the project's own fetcher asks a fake network, the pauses are counted and the clock stands still."""
import hashlib
import io
import time
import urllib.error
from datetime import datetime
from io import StringIO
from urllib.parse import quote

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.budget.management.commands import watch_finance_bill as watch
from apps.sources.services import fetch
from apps.topics.services import kit

SITE = 'https://www.chambredesrepresentants.ma'
FEED = f'{SITE}/ar/legislation/loi-discussion-assemblee/rss'
DOSSIER = f'{SITE}/ar/DossierPLF2027'
FILES = f'{SITE}/sites/default/files'


class Network:
    """The sites as a dict: url → bytes, an HTTP status or an error to raise. The opener the fetcher builds is this
    one; robots.txt answers 404 (everything allowed) unless a test gives one."""

    def __init__(self):
        self.pages, self.asked, self.slept, self.waited = {}, [], [], {}

    def open(self, request, timeout=None):
        url = request.full_url
        self.asked.append(url)
        self.waited[url] = timeout
        answer = self.pages.get(url, 404)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, int):
            raise urllib.error.HTTPError(url, answer, 'Not Found' if answer == 404 else 'Forbidden', {}, None)
        return io.BytesIO(answer)


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 21, 9, 30, 0)


@pytest.fixture
def net(monkeypatch, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    fetch._ROBOTS.clear()
    fetch._LAST.clear()
    network = Network()
    monkeypatch.setattr(fetch.urllib.request, 'build_opener', lambda *handlers: network)
    monkeypatch.setattr(time, 'sleep', network.slept.append)
    monkeypatch.setattr(watch, 'datetime', Clock)
    yield network
    fetch._ROBOTS.clear()
    fetch._LAST.clear()


def run(*args) -> str:
    out = StringIO()
    call_command('watch_finance_bill', '--year', '2027', *args, stdout=out)
    return out.getvalue()


def rss(*items: str) -> bytes:
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{"".join(items)}</channel></rss>'.encode()


def item(title=None, link=None, date=None) -> str:
    return ('<item>' + (f'<title>{title}</title>' if title is not None else '')
            + (f'<link>{link}</link>' if link is not None else '')
            + (f'<pubDate>{date}</pubDate>' if date is not None else '') + '</item>')


# The feed's links: an anchor escaped as HTML, its address escaped twice.
BILL_PAGE = '/ar/%25D8%25A7%25D9%2584%25D9%2586%25D8%25B5%25D9%2588%25D8%25B5/plf-2027'
CHAMBER_FEED = rss(
    item('&lt;p&gt;مشروع قانون المالية رقم 60.26 للسنة المالية 2027&lt;/p&gt;',
         f'&lt;a href=&quot;{BILL_PAGE}&quot; hreflang=&quot;ar&quot;&gt;مشروع&lt;/a&gt;', 'Tue, 20 Oct 2026 18:00:00 +0000'),
    item('مشروع قانون المالية للسنة المالية 2027: الجزء الثاني'),                  # no page, no date
    item('مشروع قانون التصفية المتعلق بتنفيذ قانون المالية للسنة المالية 2027', '&lt;a href=&quot;/ar/x&quot;&gt;'),
    item('مشروع قانون المالية رقم 55.25 للسنة المالية 2026', SITE),
    item(link=SITE))

AGENDA = ('<p>الأربعاء 28 أكتوبر 2026</p><p>الشروع في المناقشة العامة</p>'
          '<p>الاثنين 2 نونبر 2026 : التصويت</p>')
LINKS = ('<a href="/sites/default/files/01-%20Projet%20loi%20de%20Finances%202027_Ar.pdf">مشروع قانون المالية\n'
         '<b>رقم 60.26</b></a>'
         '<a href="/sites/default/files/02-Note.pdf">مذكرة تقديم</a>'
         '<a href="/sites/default/files/03-Rapport.pdf">التقرير الاقتصادي والمالي</a>'
         '<a href="/sites/default/files/04-Annexe.pdf">الملحق</a>'
         '<a href="https://elsewhere.example/05.pdf">ملف خارجي</a>'
         '<a href="/sites/default/files/..%2F06.pdf">ملف</a>'
         '<a href="/sites/default/files/07 ملحق.pdf">ملحق</a>'          # its address as typed: asked escaped
         '<a href="/ar/actualites">الأخبار</a>')


def dossier(agenda=AGENDA) -> bytes:
    # A script's words are no agenda line, whatever they say.
    return (f'<html><head><script>var day = `\nالخميس 1 يناير 2026\n`;</script><style>p{{}}</style></head><body>{agenda}{LINKS}'
            '</body></html>').encode()


BILL = b'%PDF-1.7 the bill'
NOTE = b'%PDF-1.4 the note'
ANNEX = b'%PDF-1.5 the annex'


def test_the_watcher_lists_the_bill_and_keeps_each_file_of_its_dossier_once_and_its_page_when_it_changes(net, tmp_path):
    page = dossier()
    net.pages.update({FEED: CHAMBER_FEED, DOSSIER: page, f'{FILES}/01-%20Projet%20loi%20de%20Finances%202027_Ar.pdf': BILL,
                      f'{FILES}/02-Note.pdf': NOTE, f'{FILES}/04-Annexe.pdf': b'<html>a page</html>',
                      f'{FILES}/..%2F06.pdf': b'%PDF-1.7', quote(f'{FILES}/07 ملحق.pdf', safe=':/%'): ANNEX})
    digest = hashlib.sha256(page).hexdigest()
    said = run('--fetch').splitlines()
    assert said == [
        'LISTED in the feed: مشروع قانون المالية رقم 60.26 للسنة المالية 2027',
        f'  {SITE}/ar/النصوص/plf-2027', '  Tue, 20 Oct 2026 18:00:00 +0000',
        'LISTED in the feed: مشروع قانون المالية للسنة المالية 2027: الجزء الثاني', '  ', '  ',
        f'dossier: changed, kept ({digest[:12]})',
        'agenda: الأربعاء 28 أكتوبر 2026', 'agenda: الاثنين 2 نونبر 2026 : التصويت',
        f'NEW  مشروع قانون المالية رقم 60.26  {FILES}/01-%20Projet%20loi%20de%20Finances%202027_Ar.pdf',
        f'NEW  مذكرة تقديم  {FILES}/02-Note.pdf',
        f'NEW  التقرير الاقتصادي والمالي  {FILES}/03-Rapport.pdf',
        '  did not answer (HTTP Error 404: Not Found); not kept',
        f'NEW  الملحق  {FILES}/04-Annexe.pdf',
        '  not a PDF: the site answered with a page; not kept',
        'NEW  ملف خارجي  https://elsewhere.example/05.pdf',
        f'  did not answer (https://elsewhere.example/05.pdf: not an address the fetchers may ask (https on '
        f'{", ".join(sorted(fetch.HOSTS))})); not kept',
        f'NEW  ملف  {FILES}/..%2F06.pdf',
        "  '../06.pdf': not a plain file name; not kept",
        f'NEW  ملحق  {FILES}/07 ملحق.pdf']
    assert net.slept == [2] * 7           # two seconds after each file asked
    folder = tmp_path / 'sources' / 'parliament' / 'plf2027'
    kept = f'dossier-2026-10-21-{digest[:8]}.html'
    assert sorted(p.name for p in folder.iterdir()) == ['01-_Projet_loi_de_Finances_2027_Ar.pdf', '02-Note.pdf',
                                                         '07_ملحق.pdf', 'MANIFEST.tsv', kept]
    assert (folder / '01-_Projet_loi_de_Finances_2027_Ar.pdf').read_bytes() == BILL and (folder / kept).read_bytes() == page
    manifest = (folder / 'MANIFEST.tsv').read_text().splitlines()
    assert manifest == [
        'file\tsource\tsha256\tbytes\ttime',
        f'{kept}\t{DOSSIER}\t{digest}\t{len(page)}\t2026-10-21T09:30:00',
        f'01-_Projet_loi_de_Finances_2027_Ar.pdf\t{FILES}/01-%20Projet%20loi%20de%20Finances%202027_Ar.pdf\t'
        f'{hashlib.sha256(BILL).hexdigest()}\t{len(BILL)}\t2026-10-21T09:30:00',
        f'02-Note.pdf\t{FILES}/02-Note.pdf\t{hashlib.sha256(NOTE).hexdigest()}\t{len(NOTE)}\t2026-10-21T09:30:00',
        f'07_ملحق.pdf\t{FILES}/07 ملحق.pdf\t{hashlib.sha256(ANNEX).hexdigest()}\t{len(ANNEX)}\t2026-10-21T09:30:00']

    # Again without --fetch, the dossier unchanged and the bill gone from the feed: the kept files are said kept, the
    # others new, and nothing is asked for or written.
    net.pages[FEED] = rss(item('مشروع قانون رقم 12.26'), item())
    net.asked.clear()
    said = run().splitlines()
    assert said[0] == 'feed: not listed (2 bills in it)' and not any(line.startswith('dossier') for line in said)
    assert said[3:5] == [f'kept مشروع قانون المالية رقم 60.26  {FILES}/01-%20Projet%20loi%20de%20Finances%202027_Ar.pdf',
                         f'kept مذكرة تقديم  {FILES}/02-Note.pdf']
    assert said[5] == f'NEW  التقرير الاقتصادي والمالي  {FILES}/03-Rapport.pdf' and len(said) == 10
    assert net.asked == [FEED, DOSSIER] and (folder / 'MANIFEST.tsv').read_text().splitlines() == manifest

    # The dossier changed (a new day on its agenda): its page is kept again, beside the first.
    changed = dossier(AGENDA + '<p>الجمعة 6 نونبر 2026</p>')
    net.pages[DOSSIER] = changed
    said = run().splitlines()
    new_digest = hashlib.sha256(changed).hexdigest()
    assert said[1:5] == [f'dossier: changed, kept ({new_digest[:12]})', 'agenda: الأربعاء 28 أكتوبر 2026',
                         'agenda: الاثنين 2 نونبر 2026 : التصويت', 'agenda: الجمعة 6 نونبر 2026']
    assert (folder / f'dossier-2026-10-21-{new_digest[:8]}.html').read_bytes() == changed
    assert len((folder / 'MANIFEST.tsv').read_text().splitlines()) == 6


@pytest.mark.django_db
def test_the_press_watch_lists_the_outlets_new_articles_about_the_bill_and_passes_an_outlet_that_does_not_answer(net):
    held = kit.load('tax')['pages']['bill-press']['items']
    known = held[0]['url']
    net.pages.update({
        'https://www.hespress.com/feed': rss(
            item('<![CDATA[مشروع قانون المالية لسنة 2027 أمام لجنة المالية]]>', 'https://www.hespress.com/a-1.html',
                 'Wed, 28 Oct 2026 10:00:00 +0000'),
            item('مالية 2027: ما قالته النقابات', known),                       # on the press page already
            item('مشروع قانون المالية لسنة 2026', 'https://www.hespress.com/old.html'),
            item('مباراة في كرة القدم', 'https://www.hespress.com/sport.html')),
        'https://fr.hespress.com/feed': rss(item('PLF 2027 : ce qui change', 'https://fr.hespress.com/b?x=1&amp;y=2')),
        'https://www.telquel.ma/feed': rss(item('La loi de finances pour 2027 au Parlement', 'https://www.telquel.ma/c')),
        'https://www.leseco.ma/robots.txt': 403,
        FEED: rss(), DOSSIER: b'<html></html>'})
    said = run('--press').splitlines()
    assert said[:9] == [
        'press: https://medias24.com/feed/ did not answer (HTTP Error 404: Not Found)',
        'press: https://www.leseco.ma/feed/ did not answer (https://www.leseco.ma refuses its robots.txt to us (403): '
        'nothing fetched; ask the site)',
        'PRESS Wed, 28 Oct 2026 10:00:00 +0000  مشروع قانون المالية لسنة 2027 أمام لجنة المالية',
        '  https://www.hespress.com/a-1.html',
        'PRESS   PLF 2027 : ce qui change', '  https://fr.hespress.com/b?x=1&y=2',
        'PRESS   La loi de finances pour 2027 au Parlement', '  https://www.telquel.ma/c',
        f'press: 3 new item(s) for a person to read (pages/bill-press holds {len({i["url"] for i in held})})']
    assert said[9] == 'feed: not listed (0 bills in it)'
    # A press feed is waited for a minute at most, the Chamber two.
    assert (net.waited['https://www.hespress.com/feed'], net.waited[FEED], net.waited[DOSSIER]) == (60, 120, 120)


def test_a_chamber_that_refuses_the_watcher_stops_it_with_the_reason(net):
    net.pages[f'{SITE}/robots.txt'] = 403
    with pytest.raises(CommandError, match=r'refuses its robots\.txt to us \(403\): nothing fetched; ask the site'):
        run()
    assert net.asked == [f'{SITE}/robots.txt']
