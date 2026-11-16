"""`process_issue`, one issue end to end (the pipeline's steps as the nightly fetch runs them): the PDF registered, the
contents and the texts read by the model (its answers come from a stand-in for the API), the texts loaded at their
addresses and their links read; a French issue's texts kept beside the Arabic ones. Nothing is paid without --write."""
import json
from datetime import date
from io import StringIO

import pypdfium2 as pdfium
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.corpus.models import Article, Text
from apps.corpus.services import llm
from apps.corpus.tests import claude
from apps.corpus.tests.test_recut import PAGES, TOC
from apps.sources.models import Document, Edition, Issue, Page
from apps.sources.services.ocr import SpendingNotAllowed
from apps.translations.models import FrenchArticle, FrenchText

pytestmark = pytest.mark.django_db

DATA = {'found': True, 'type': 'law', 'number_as_printed': '10.20', 'title': 'قانون رقم 10.20 يتعلق بالشغل المنزلي',
        'signed_on_gregorian': '2025-02-20', 'signed_on_hijri': '', 'authority': '', 'promulgating_dahir': '1.25.02',
        'preamble': [], 'closing': '', 'signatories': [], 'cites': [], 'amends': []}
ORDER = {'section': 'special', 'rubric': '', 'type': 'order', 'number_as_printed': '148.25',
         'title': 'قرار لوزير التشغيل رقم 148.25 صادر في 12 من رجب 1446 (13 يناير 2025) بتتميم لائحة',
         'signed_on_gregorian': '2025-01-13', 'signed_on_hijri': '', 'page': 1531}


def bulletin(pages, edition=Edition.GENERAL_AR, first=1529):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{edition}7383'.ljust(64, '0'),
                                  path='BO_7383.pdf', mime='application/pdf', language=edition[-2:], bytes=1,
                                  fetched_at=timezone.now(), page_count=len(pages))
    for i, text in enumerate(pages):
        Page.objects.create(document=doc, index=i, printed_number=first + i, text=text)
    return Issue.objects.create(edition=edition, number=7383, date=date(2025, 3, 3), document=doc,
                                first_page_number=first)


def run(*args, **opts) -> str:
    out = StringIO()
    call_command('process_issue', *args, stdout=out, **opts)
    return out.getvalue()


def test_an_issue_is_read_cut_loaded_and_linked_and_what_it_cost_is_in_the_ledger(tmp_path, settings, monkeypatch):
    # The order's description is lost (the API could not answer it): it is not loaded.
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: {
        'toc-7383': {'entries': [*TOC, ORDER]}, 't0': DATA}.get(cid))
    issue = bulletin(PAGES)
    runs = tmp_path / 'reports' / 'runs'
    runs.mkdir(parents=True)
    (runs / 'queue_2019_2026.txt').write_text('7383 2025-03-03 https://example.org/BO_7383_ar.pdf\n')
    said = run('7383', '--write', steps='toc,texts,load,links')
    assert 'table of contents: 2 texts' in said and 'texts read: 1 of 2' in said
    assert "loaded: {" in said and 'links: ' in said
    work = tmp_path / 'reports' / 'issues' / '7383'
    assert json.loads((work / 'toc.json').read_text()) == [*TOC, ORDER]
    item, lost = json.loads((work / 'texts.json').read_text())
    assert (lost['data'], lost['stop']) == (None, 'errored') and not Text.objects.filter(number='148-25').exists()
    assert item['data'] == DATA and [a['label'] for a in item['articles']] == ['المادة الأولى', 'المادة 2']
    law = Text.objects.get(akn_uri='/akn/ma/act/loi/10-20')
    assert law.first_published_in == issue and law.promulgating_dahir == '1.25.02'
    assert Article.objects.filter(version__text=law).count() == 2
    # The model read the contents from the first pages, then the text from its own lines, each page marked.
    toc, text, _ = sent.requests()
    assert toc['params']['model'] == 'claude-haiku-5-5' and '=== الصفحة 1529 ===' in toc['params']['messages'][0]['content']
    assert text['params']['messages'][0]['content'].startswith('[ص 1530] ظهير شريف رقم 1.25.02')
    assert [(e['kind'], e['request'], e['cost_usd']) for e in llm.ledger() if 'request' in e] == [
        ('toc:7383', 'toc-7383', 0.0002), ('texts:7383', 't0', 0.0002)]       # an unanswered request costs nothing
    assert llm.total_spent() > 0
    # The coverage line counts the issue: two legal texts listed, one loaded, the order not found.
    line = json.loads((tmp_path / 'reports' / 'coverage.json').read_text())['7383']
    assert {k: line[k] for k in ('date', 'listed', 'loaded', 'unfound')} == {
        'date': '2025-03-03', 'listed': 2, 'loaded': 1, 'unfound': 1}


def test_nothing_is_sent_to_the_model_without_write(tmp_path, settings, monkeypatch):
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: {'entries': TOC})
    bulletin(PAGES)
    with pytest.raises(SpendingNotAllowed):
        run('7383', steps='toc')
    assert sent.requests() == [] and not (tmp_path / 'reports' / 'issues' / '7383' / 'toc.json').exists()


def test_a_contents_cut_at_the_token_limit_is_read_again_in_two_halves(tmp_path, settings, monkeypatch):
    early = {**TOC[0], 'number_as_printed': '9.20', 'page': 1529}
    answers = {'toc-7383': ('{"entries": [{"section": "gen', 'max_tokens'),
               'toc-7383-0': {'entries': [early, TOC[0]]}, 'toc-7383-1': {'entries': [early, TOC[0]]}}
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: answers[cid])
    bulletin(PAGES)
    said = run('7383', '--write', steps='toc')
    assert 'table of contents cut: read again in two halves' in said
    # Each half keeps only the entries on its side of the middle page (1530): none is counted twice.
    assert json.loads((tmp_path / 'reports' / 'issues' / '7383' / 'toc.json').read_text()) == [early, TOC[0]]
    halves = [r['params']['system'] for r in sent.requests()[1:]]
    assert halves[0].endswith('Return only the entries whose page is before 1530.')
    assert halves[1].endswith('Return only the entries whose page is 1530 or after.')


@pytest.mark.parametrize('halves', [False, True])
def test_a_contents_the_model_could_not_read_stops_the_issue(tmp_path, settings, monkeypatch, halves):
    claude.install(monkeypatch, settings, tmp_path, lambda cid, params: None)
    bulletin(PAGES)
    with pytest.raises(RuntimeError, match='table of contents not read: errored'):
        run('7383', '--write', steps='toc', toc_halves=halves)


def test_ingest_registers_the_pdf_and_needs_the_issues_day(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    with pytest.raises(CommandError, match='--date is needed'):
        run('7600', steps='ingest')
    pdf = pdfium.PdfDocument.new()
    for _ in range(2):
        pdf.new_page(595, 842)
    (tmp_path / 'issues' / 'bo_ar').mkdir(parents=True)
    pdf.save(str(tmp_path / 'issues' / 'bo_ar' / 'BO_7600-bis_ar.pdf'))
    said = run('7600-bis', steps='ingest,number', date='2026-11-02', url='https://example.org/BO_7600-bis_ar.pdf')
    issue = Issue.objects.get(number=7600, suffix='bis')
    assert said.startswith(f'registered {issue}: 2 pages\nprinted pages start at ')
    assert (issue.date, issue.document.url, issue.document.pages.count()) == (
        date(2026, 11, 2), 'https://example.org/BO_7600-bis_ar.pdf', 2)


FRENCH = [
    'BULLETIN OFFICIEL\nSOMMAIRE\nTEXTES GENERAUX\nDahir n° 1-25-02 du 20 février 2025 portant promulgation de la loi '
    'n° 10-20 relative au travail domestique . . . . . . 120',
    'Dahir n° 1-25-02 du 21 chaabane 1446 (20 février 2025) portant promulgation de la loi n° 10-20 relative au '
    'travail domestique.\nLOUANGE A DIEU SEUL !\nArticle premier. – La présente loi s\'applique aux travailleurs '
    'domestiques.\nArticle 2. – Elle entre en vigueur dès sa publication.\nFait à Rabat, le 20 février 2025.',
]
FRENCH_TOC = [{'section': 'general', 'rubric': '', 'type': 'law', 'number_as_printed': '10-20',
               'title': 'Dahir n° 1-25-02 du 20 février 2025 portant promulgation de la loi n° 10-20 relative au '
                        'travail domestique', 'signed_on_gregorian': '2025-02-20', 'signed_on_hijri': '', 'page': 120}]


def test_a_french_issue_reads_its_contents_and_keeps_each_text_beside_the_arabic(tmp_path, settings, monkeypatch):
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: {'toc-fr-7383': {'entries': FRENCH_TOC}}[cid])
    bulletin(FRENCH, edition=Edition.TRANSLATION_FR, first=119)
    said = run('7383', '--write', edition=Edition.TRANSLATION_FR, steps='toc,texts,load,links')
    assert said.endswith("table of contents: 1 texts\nloaded: {'texts': 1, 'articles': 2, 'not_found': 0, 'no_number': 0}\n")
    assert json.loads((tmp_path / 'reports' / 'issues' / 'fr-7383' / 'toc.json').read_text()) == FRENCH_TOC
    [toc] = sent.requests()
    assert toc['params']['messages'][0]['content'].startswith('=== Page 119 ===\nBULLETIN OFFICIEL\nSOMMAIRE')
    assert 'before 1956' not in toc['params']['system']           # a 2025 issue: no word of the old Bulletin's forms
    french = FrenchText.objects.get(text_uri='/akn/ma/act/loi/10-20')
    assert (french.number, french.issue_number, french.pages) == ('10-20', 7383, '120-120')
    assert (french.type, french.signed_on, french.issue_date, french.title) == (
        'law', date(2025, 2, 20), date(2025, 3, 3), FRENCH_TOC[0]['title'])
    assert list(FrenchArticle.objects.order_by('order').values_list('label', 'number', 'body')) == [
        ('Article premier', '1', "La présente loi s'applique aux travailleurs domestiques."),
        ('Article 2', '2', 'Elle entre en vigueur dès sa publication.')]


def test_a_french_contents_the_model_could_not_read_is_said(tmp_path, settings, monkeypatch):
    claude.install(monkeypatch, settings, tmp_path, lambda cid, params: None)
    bulletin(FRENCH, edition=Edition.TRANSLATION_FR, first=119)
    with pytest.raises(RuntimeError, match='table of contents not read: errored'):
        run('7383', '--write', edition=Edition.TRANSLATION_FR, steps='toc')


FRENCH_MORE = FRENCH[:1] + [
    FRENCH[1] + '\nArrêté du ministre de l\'emploi relatif au travail domestique.\n'
    'Décision du Conseil de la concurrence n° 12/25 du 3 mars 2025 relative au marché des carburants.\n'
    'Le Conseil de la concurrence,\nVu la loi n° 104-12 ;\nDécide la publication de son avis sur le marché.',
]
MORE_TOC = FRENCH_TOC + [
    {'section': 'special', 'rubric': '', 'type': 'decision', 'number_as_printed': '12/25', 'signed_on_gregorian': '',
     'title': 'Décision du Conseil de la concurrence n° 12/25 du 3 mars 2025', 'signed_on_hijri': '', 'page': 120},
    {'section': 'special', 'rubric': '', 'type': 'decision', 'number_as_printed': '13/25', 'signed_on_gregorian': '2025-03-04',
     'title': 'Décision du Conseil de la concurrence n° 13/25 du 4 mars 2025', 'signed_on_hijri': '', 'page': 120},
    {'section': 'other', 'rubric': '', 'type': 'other', 'number_as_printed': '', 'signed_on_gregorian': '',
     'title': 'Avis aux importateurs', 'signed_on_hijri': '', 'page': 121},
    {'section': 'general', 'rubric': '', 'type': 'decree', 'number_as_printed': '2-25-999', 'signed_on_gregorian': '',
     'title': 'Décret n° 2-25-999 relatif aux carburants', 'signed_on_hijri': '', 'page': 121},
]


def test_a_french_issue_keeps_a_text_without_articles_whole_beside_the_arabic_of_its_number():
    from apps.corpus.services import french
    issue = bulletin(FRENCH_MORE, edition=Edition.TRANSLATION_FR, first=119)
    held = Text.objects.create(akn_uri='/akn/ma/act/decision/2025/12-25', type='decision', number='12-25',
                               title_ar='قرار مجلس المنافسة رقم 12/25')
    # A decision's number names no address of its own: two rows hold it, and the French goes to the first one made.
    later = Text.objects.create(akn_uri='/akn/ma/act/decision/2025/12-25-bo7384', type='decision', number='12-25',
                                title_ar='قرار مجلس المنافسة رقم 12/25')
    assert french.load(issue, MORE_TOC) == {'texts': 2, 'articles': 3, 'not_found': 2, 'no_number': 1}
    assert not FrenchText.objects.filter(text_uri=later.akn_uri).exists()
    assert Text.objects.get(pk=later.pk).title_fr == ''
    decision = FrenchText.objects.get(text_uri=held.akn_uri)
    [whole] = FrenchArticle.objects.filter(text_uri=held.akn_uri)
    # Another text's heading on the way is passed over; its words run from the line naming it.
    assert (whole.label, whole.number) == ('', '') and whole.body.startswith('Décision du Conseil de la concurrence n° 12/25')
    assert whole.body.endswith('Décide la publication de son avis sur le marché.') and decision.pages == '120-120'
    assert Text.objects.get(pk=held.pk).title_fr == MORE_TOC[1]['title']
    # Loaded again, the issue's French is replaced, not doubled.
    french.load(issue, MORE_TOC)
    assert FrenchText.objects.count() == 2 and FrenchArticle.objects.count() == 3
