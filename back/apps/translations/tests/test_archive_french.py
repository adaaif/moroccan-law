"""`archive_french` (A of the Bulletin-from-No.-1 review): the French issues before 1926 registered, read page by page, their
contents read, each official entry matched against the Arabic issues of its weeks, and the texts only the French
printed cut and translated, a worker taking its issues a chunk at a time. The scans are real image-only PDFs; the
model's answers come from a stand-in for the API, in its shapes."""
import json
import re
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.corpus.services import llm
from apps.corpus.services.issue_structure import TOC_SCHEMA
from apps.corpus.tests import claude
from apps.sources.models import Document, Edition, Issue, OcrRun, Page
from apps.sources.services import archive
from apps.sources.services.ocr import SpendingNotAllowed
from apps.translations.management.commands.archive_french import ARABIC_NOTE, MATCH_SYSTEM
from apps.translations.models import FrenchArticle, FrenchText
from apps.translations.tests.files import scan_pdf

pytestmark = pytest.mark.django_db


def run(*args, **opts) -> str:
    out = StringIO()
    call_command('archive_french', *args, stdout=out, **opts)
    return out.getvalue()


def plans(tmp_path, french, arabic=()):
    """The French issues to read, and the Arabic edition's (archive/plan.json), each {key: date}."""
    folder = tmp_path / 'archive'
    folder.mkdir(exist_ok=True)
    (folder / 'plan_fr.json').write_text(json.dumps({'issues': [
        {'key': k, 'date': d, 'url': f'https://example.org/BO_{k}_fr.pdf', 'path': f'1913/BO_{k}_fr.pdf'}
        for k, d in french.items()]}))
    (folder / 'plan.json').write_text(json.dumps({'pilot': [], 'issues': [
        {'key': k, 'year': 1913, 'date': d, 'url': '', 'path': f'1913/BO_{k}_Ar.pdf'} for k, d in dict(arabic).items()]}))


def contents(tmp_path, key, entries):
    work = tmp_path / 'reports' / 'issues' / key
    work.mkdir(parents=True, exist_ok=True)
    (work / 'toc.json').write_text(json.dumps(entries, ensure_ascii=False))


def entry(title, kind='dahir', page=561, day='1913-08-12', section='general'):
    return {'section': section, 'rubric': '', 'type': kind, 'number_as_printed': '', 'title': title,
            'signed_on_gregorian': day, 'signed_on_hijri': '', 'page': page}


DOC = entry('Dahir du 12 août 1913 (9 ramadan 1331) formant code des obligations et des contrats')
COURTS = entry("Dahir du 12 août 1913 (9 ramadan 1331) relatif à l'organisation judiciaire du Protectorat", page=562)
NOTICE = entry('Avis aux importateurs', kind='other', page=562, day='', section='other')
POST = entry('Arrêté viziriel du 20 août 1913 portant création d’un bureau de poste à Mazagan', kind='order', page=562,
             day='1913-08-20')
# An Arabic issue's entry, its title longer than the match is shown.
CAID = 'ظهير شريف بتعيين قائد على ' + 'قبيلة ' * 30
# BO 46 of 12 September 1913 as Haiku reads it: its contents page whole (cut at the token limit the first time, then
# read in two halves), its next page by columns.
CONTENTS = ('561 BULLETIN OFFICIEL N° 46\nSOMMAIRE\n'
            'Dahir du 12 août 1913 formant code des obligations et des contrats . . . . 561\n'
            "Dahir du 12 août 1913 relatif à l'organisation judiciaire du Protectorat . . . . 562\n"
            'Avis aux importateurs . . . . 562\n'
            'DAHIR DU 12 AOUT 1913 (9 ramadan 1331)\nformant code des obligations et des contrats.\n'
            'Article premier. – Les obligations dérivent des conventions.')
LEFT = ('Les autres obligations dérivent de la loi.\nFait à Rabat, le dix août.\n'
        "DAHIR DU 12 AOUT 1913 (9 ramadan 1331)\nrelatif à l'organisation judiciaire du Protectorat.\n"
        'Article premier. – Il est institué des tribunaux de première instance.')
RIGHT = 'Art. 2. – Ils jugent selon la loi.\nAVIS AUX IMPORTATEURS\nLes importateurs sont avisés.'
ARABIC = {'title': 'ظهير شريف مؤرخ في 12 غشت 1913 يتعلق بالتنظيم القضائي للحماية',
          'articles': [{'key': 'a0', 'label': 'الفصل الأول', 'body': 'تحدث محاكم ابتدائية.'},
                       {'key': 'a1', 'label': 'الفصل 2', 'body': 'تحكم وفقا للقانون.'}]}


def test_the_texts_only_the_french_printed_are_read_matched_cut_and_translated(tmp_path, settings, monkeypatch):
    # The match answers for two of the three official entries: the one it leaves out is never taken for French only.
    answers = {'toc-fr-46': {'entries': [DOC, COURTS, POST, NOTICE]},
               'match-fr-46': {'pairs': [{'fr': 0, 'ar': ''}, {'fr': 1, 'ar': ''}]}, 't0': ARABIC}
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: answers.get(cid))
    plans(tmp_path, {'46': '1913-09-12', '47': '1913-09-19'},
          arabic={'15': '1913-08-01', '19': '1913-09-13', '20': '1913-10-10'})       # 15 is weeks before 46
    contents(tmp_path, '15', [{'section': 'general', 'type': 'dahir', 'title': 'ظهير شريف سابق', 'page': 1}])
    contents(tmp_path, '19', [{'section': 'general', 'type': 'dahir', 'title': CAID, 'page': 1,
                               'signed_on_gregorian': '1913-08-30'},
                              {'section': 'other', 'type': 'other', 'title': 'إعلان', 'page': 2}])
    scan_pdf(tmp_path / 'pdfs' / '1913' / 'BO_46_fr.pdf', ['across', 'columns'])
    scan_pdf(tmp_path / 'pdfs' / '1913' / 'BO_47_fr.pdf', ['across'])
    assert run('register', pdfs=str(tmp_path / 'pdfs')).rstrip().endswith('registered 2; 2 French issues')
    issue = Issue.objects.get(edition=Edition.TRANSLATION_FR, number=46)
    first, second = issue.document.pages.order_by('index')
    unread = Page.objects.get(document__issue__number=47)                # the API will not answer its reading
    upper, lower = CONTENTS.split('\nAvis')[0], 'Avis' + CONTENTS.split('\nAvis')[1]     # cut between two lines
    answers.update({f'p{first.pk}': (CONTENTS[:90], 'max_tokens'), f'p{first.pk}s0': upper, f'p{first.pk}s1': lower,
                    f'p{second.pk}c0': LEFT, f'p{second.pk}c1': RIGHT})

    # Read: the page printed across whole, the page in two columns column by column; a reading cut at the token
    # limit read again in halves; the folios from the heads. An issue a page of which is left unread is set aside.
    assert 'fr-read 46,47: $' in run('work', 'read', '--write')
    assert [r['custom_id'] for r in sent.requests()] == [f'p{first.pk}', f'p{unread.pk}', f'p{second.pk}c0',
                                                         f'p{second.pk}c1', f'p{first.pk}s0', f'p{first.pk}s1']
    assert (archive.root() / 'state' / 'fr-read' / '47.error').read_text() == '1 pages left unread'
    assert not (archive.root() / 'doubts-fr' / '47.json').exists()
    assert [(r.page.index, r.variant) for r in OcrRun.objects.order_by('page__index', 'pk')] == [
        (0, 'page-1596'), (0, 'strips-3192'), (1, 'columns-3192')]
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.printed_number, first.text) == (561, CONTENTS) and second.text == f'{LEFT}\n\n{RIGHT}'
    assert json.loads((archive.root() / 'state' / 'fr-read' / '46.done').read_text()) == {
        'pages': 2, 'doubts': 0, 'first_page': 561}
    assert json.loads((archive.root() / 'doubts-fr' / '46.json').read_text()) == {'median': 1.15, 'pages': []}
    assert not list((tmp_path / 'renders' / issue.document.sha256[:16]).glob('*.png'))       # the images go

    # The contents, from the first pages as read.
    assert 'fr-toc 46: $' in run('work', 'toc', '--write')
    toc = sent.requests()[-1]['params']
    assert toc['messages'][0]['content'] == f'=== Page 561 ===\n{CONTENTS}\n\n=== Page 562 ===\n{LEFT}\n\n{RIGHT}'
    assert (toc['model'], toc['max_tokens'], toc['output_config']['format']['schema']) == (
        'claude-haiku-5-5', 32000, TOC_SCHEMA)
    assert 'PARTIE NON OFFICIELLE' in toc['system']                     # the old issues' two parts
    assert json.loads((tmp_path / 'reports' / 'issues' / 'fr-46' / 'toc.json').read_text()) == [DOC, COURTS, POST,
                                                                                                 NOTICE]
    assert json.loads((archive.root() / 'state' / 'fr-toc' / '46.done').read_text()) == {
        'entries': 4, 'official': 3, 'kinds': {'dahir': 2, 'order': 1, 'other': 1}}

    # The match: the official entries against the Arabic issues of three weeks before to four months after.
    run('work', 'match', '--write')
    match = sent.requests()[-1]['params']
    assert (match['max_tokens'], match['system']) == (8000, MATCH_SYSTEM)
    assert json.loads(match['messages'][0]['content']) == {
        'french_issue': {'number': '46', 'date': '1913-09-12', 'entries': [
            {'fr': i, 'type': e['type'], 'signed': e['signed_on_gregorian'], 'title': e['title']}
            for i, e in enumerate([DOC, COURTS, POST])]},
        'arabic_entries': [{'id': '19:0', 'date': '1913-09-13', 'type': 'dahir', 'signed': '1913-08-30',
                            'title': CAID[:160]}]}
    assert json.loads((tmp_path / 'reports' / 'issues' / 'fr-46' / 'match.json').read_text()) == {
        'pairs': {'0': '', '1': '', '2': '?'}, 'alone': [0, 1]}
    assert json.loads((archive.root() / 'state' / 'fr-match' / '46.done').read_text()) == {'official': 3, 'alone': 2}

    # The texts: the code of obligations is held from Adala, so the courts' dahir alone is cut and translated.
    run('work', 'texts', '--write')
    uri = '/akn/ma/act/dahir/1913-09-12/bofr46-2'
    assert list(FrenchText.objects.values_list('text_uri', flat=True)) == [uri]
    assert [(a.label, a.body, a.printed_page) for a in FrenchArticle.objects.filter(text_uri=uri)] == [
        ('Article premier', 'Il est institué des tribunaux de première instance.', 562),
        ('Art. 2', 'Ils jugent selon la loi.', 562)]
    assert json.loads((archive.root() / 'state' / 'fr-texts' / '46.done').read_text()) == {
        'texts': 1, 'articles': 2, 'not_found': 0, 'no_number': 0, 'alone': 1}
    translated = json.loads((archive.root() / 'translated' / 'bo_46_fr.json').read_text())
    assert translated['arabic'] == ARABIC_NOTE and [t['text_uri'] for t in translated['texts']] == [uri]
    assert [a['body_ar'] for a in translated['texts'][0]['articles']] == ['تحدث محاكم ابتدائية.', 'تحكم وفقا للقانون.']

    # Each batch in the ledger under its phase and its chunk.
    assert {e['request']: e['kind'] for e in llm.ledger() if e.get('request') in ('toc-fr-46', 'match-fr-46', 't0')} == {
        'toc-fr-46': 'toc-fr:46+0', 'match-fr-46': 'match-fr:46+0', 't0': 'translate-french'}
    said = run('status')
    assert said.splitlines()[:4] == ['fr-read: 1 of 2 done, 1 errors', 'fr-toc: 1 of 2 done, 0 errors',
                                     'fr-match: 1 of 2 done, 0 errors', 'fr-texts: 1 of 2 done, 0 errors']
    assert Decimal(said.splitlines()[4].removeprefix('spent: ')) == Decimal('0.0016')     # eight answers, $0.0002 each


def test_register_links_each_plans_pdf_once_and_status_counts_the_phases(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    with pytest.raises(CommandError, match=re.escape('plan_fr.json is missing')):
        run('status')
    with pytest.raises(CommandError, match='--pdfs is needed'):
        run('register')
    with pytest.raises(CommandError, match='work needs a phase: read, toc, match or texts'):
        run('work')
    plans(tmp_path, {'47': '1913-09-19', '48-bis': '1913-09-26'})
    pdfs = tmp_path / 'pdfs'
    scan_pdf(pdfs / '1913' / 'BO_48-bis_fr.pdf', ['columns'])
    fetched = scan_pdf(tmp_path / 'issues' / 'bo_fr' / 'BO_47_fr.pdf', ['across'])     # fetched before: kept as it is
    assert run('register', pdfs=str(pdfs)).rstrip().endswith('registered 2; 2 French issues')
    assert run('register', pdfs=str(pdfs)).rstrip().endswith('registered 0; 2 French issues')
    assert not fetched.is_symlink()
    assert (tmp_path / 'issues' / 'bo_fr' / 'BO_48-bis_fr.pdf').resolve() == pdfs / '1913' / 'BO_48-bis_fr.pdf'
    issue = Issue.objects.get(edition=Edition.TRANSLATION_FR, number=48)
    assert (issue.suffix, issue.date, issue.document.url, issue.document.meta['archive'], issue.document.language) == (
        'bis', date(1913, 9, 26), 'https://example.org/BO_48-bis_fr.pdf', '1913/BO_48-bis_fr.pdf', 'fr')
    assert Issue.objects.get(number=47).document.path == 'issues/bo_fr/BO_47_fr.pdf'
    archive.mark('fr-read', '47', 'done')
    archive.mark('fr-read', '48-bis', 'error', 'Traceback …')
    archive.mark('fr-toc', '47', 'done')
    said = run('status')
    assert said.splitlines()[:4] == ['fr-read: 1 of 2 done, 1 errors', 'fr-toc: 1 of 2 done, 0 errors',
                                     'fr-match: 0 of 2 done, 0 errors', 'fr-texts: 0 of 2 done, 0 errors']


def held(key, pages):
    """A French issue registered, its pages as read."""
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=key.ljust(64, '0'),
                                  path=f'issues/bo_fr/BO_{key}_fr.pdf', mime='application/pdf', language='fr',
                                  bytes=1, fetched_at=timezone.now(), page_count=len(pages))
    for i, text in enumerate(pages):
        Page.objects.create(document=doc, index=i, printed_number=601 + i, text=text)
    number, suffix = Issue.parse_key(key)
    return Issue.objects.create(edition=Edition.TRANSLATION_FR, number=number, suffix=suffix, date=date(1914, 3, 6),
                                document=doc)


@pytest.fixture
def ready(tmp_path, settings, monkeypatch):
    """Issues read and waiting for their contents: 70 and 72 with words on their pages, 71 with none, 73 not read
    yet, 74 in the plan and not registered. The model answers 70's and 73's contents and not 72's."""
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: {
        'toc-fr-70': {'entries': [NOTICE]}, 'toc-fr-73': {'entries': [NOTICE]}}.get(cid))
    plans(tmp_path, dict.fromkeys(('70', '71', '72', '73', '74'), '1914-03-06'))
    for key, text in (('70', 'SOMMAIRE'), ('71', ''), ('72', 'SOMMAIRE'), ('73', 'SOMMAIRE')):
        held(key, [text])
    for key in ('70', '71', '72', '74'):
        archive.mark('fr-read', key, 'done')
    return sent


def test_a_worker_takes_its_chunks_and_sets_aside_an_issue_it_could_not_read(ready, tmp_path):
    said = run('work', 'toc', '--write', chunk=2)
    assert 'fr-toc 70,71: $' in said and 'fr-toc 72: $' in said
    assert said.rstrip().endswith('fr-toc: nothing left for this worker')
    assert archive.done('fr-toc', '70') and not archive.done('fr-toc', '73')            # 73 is not read yet
    errors = archive.root() / 'state' / 'fr-toc'
    assert (errors / '71.error').read_text() == 'no text on the contents pages'
    assert (errors / '72.error').read_text() == 'contents not read: errored'
    assert [r['custom_id'] for r in ready.requests()] == ['toc-fr-70', 'toc-fr-72']
    # An issue set aside is not offered again until its error is cleared; one read since is; a worker stops at its
    # limit, what is left for the next.
    archive.mark('fr-read', '73', 'done')
    (errors / '72.error').unlink()
    run('work', 'toc', '--write', keys='71,73,72', limit=1, chunk=1)
    assert archive.done('fr-toc', '73') and [r['custom_id'] for r in ready.requests()][2:] == ['toc-fr-73']
    assert not (errors / '71.claim').exists() and not (errors / '72.error').exists()


def test_a_worker_stops_alone_when_unasked_out_of_credit_over_budget_or_refused(ready, settings):
    with pytest.raises(SpendingNotAllowed):
        run('work', 'toc', keys='70')
    state = archive.root() / 'state' / 'fr-toc'
    assert not (state / '70.claim').exists() and not (state / '70.error').exists()
    ready.refusals = [(400, 'Your credit balance is too low to access the Anthropic API.')]
    assert 'out of credit: Your credit balance is too low' in run('work', 'toc', '--write', keys='70')
    assert not archive.done('fr-toc', '70') and not (state / '70.claim').exists()        # left for another worker
    # Refused for another reason: the chunk set aside with the traceback, the worker going on.
    ready.refusals = [(401, 'invalid x-api-key')]
    said = run('work', 'toc', '--write', keys='70')
    assert 'fr-toc 70: error, see state/fr-toc/<key>.error' in said
    assert 'invalid x-api-key' in (state / '70.error').read_text()
    (state / '70.error').unlink()
    settings.OCR_BUDGET_USD = 0.0
    assert 'budget reached: ' in run('work', 'toc', '--write', keys='70')
    assert 'worst case' in (archive.root() / 'STOP_BUDGET').read_text()
    assert run('work', 'toc', '--write', keys='70').rstrip().endswith('stopped: STOP_BUDGET: ' + (
        archive.root() / 'STOP_BUDGET').read_text().strip())
    assert ready.requests() == [] and not archive.done('fr-toc', '70')


def test_an_issue_with_no_official_entry_asks_nothing_and_has_nothing_to_translate(tmp_path, settings, monkeypatch):
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: None)       # the API answers nothing
    plans(tmp_path, {'80': '1914-03-06', '81': '1914-03-06'})
    for key in ('80', '81'):
        held(key, ['AVIS AUX IMPORTATEURS\nLes importateurs sont avisés.'])
        archive.mark('fr-toc', key, 'done')
    contents(tmp_path, 'fr-80', [NOTICE])
    contents(tmp_path, 'fr-81', [{**COURTS, 'page': 601}, NOTICE])
    said = run('work', 'match', '--write')
    assert [r['custom_id'] for r in sent.requests()] == ['match-fr-81']
    assert json.loads((tmp_path / 'reports' / 'issues' / 'fr-80' / 'match.json').read_text()) == {'pairs': {}, 'alone': []}
    assert (archive.root() / 'state' / 'fr-match' / '81.error').read_text() == 'not matched: errored'
    assert 'fr-match 80,81: $' in said
    run('work', 'texts', '--write')
    assert json.loads((archive.root() / 'state' / 'fr-texts' / '80.done').read_text()) == {
        'texts': 0, 'articles': 0, 'not_found': 0, 'no_number': 0, 'alone': 0}
    assert not FrenchText.objects.exists() and not (archive.root() / 'translated').exists()
