"""B9 of the search plan: `draft_surrogates` sends the articles not read yet (the shelf's, or the texts named) to Haiku (a
stand-in for the API) in groups under their text's name, each article keyed by a letter; the answers are kept by address,
version and prompt, a search that copies the article or gives its number dropped, and an article read with this prompt
and version is never sent again. B15 reads the facts back."""
import json
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command

from apps.corpus.models import Text
from apps.corpus.tests import claude
from apps.search.models import SearchEntry
from apps.search.services import surrogates
from apps.search.services.search import bm25

pytestmark = pytest.mark.django_db

# Eight searches, one a register in turn (msa, msa, darija, darija, darija_latin, french, english, professional).
SEARCHES = ['واش خاصني نخلص الكراء', 'يؤدي المكتري الكراء في وقتو', 'المادة 2 من قانون الكراء', ' ',
            'wach khassni nkhalles lkra', 'payer le loyer', 'pay the rent', 'المادة 2 من القانون 91.97']


@pytest.fixture
def index(settings):
    """A law of five articles (one only says it was repealed; one read already with this prompt, one with an older
    one) and the code of obligations, on the shelf."""
    Text.objects.create(akn_uri='/akn/ma/act/code/doc', type='code', number='doc', title_ar='قانون الالتزامات والعقود')
    bm25._shelf_paths.cache_clear()
    SearchEntry.objects.create(kind='text', text_path='/ma/loi/91-97', path='/ma/loi/91-97', text_type='law',
                               name={'ar': 'قانون الكراء'}, title='القانون رقم 91.97')
    SearchEntry.objects.create(kind='text', text_path='/ma/code/doc', path='/ma/code/doc', text_type='code', name={},
                               title='ظهير ' + 'ع' * 200)
    for order, path, label, body in [
            (2, '/ma/loi/91-97/art_2', 'المادة 2', 'يؤدي المكتري الكراء في أجل أقصاه 15 يوما.'),
            (1, '/ma/loi/91-97/art_1', 'المادة 1', 'يطبق هذا القانون على الكراء.'),
            (3, '/ma/loi/91-97/art_3', 'المادة 3', '(نسخت)'),
            (4, '/ma/loi/91-97/art_4', 'المادة 4', 'يمكن الإفراغ بحكم.'),
            (5, '/ma/loi/91-97/art_5', 'المادة 5', 'نص بلا جواب.'),
            (1, '/ma/code/doc/art_1', 'الفصل 1', 'الالتزام عقد.')]:
        SearchEntry.objects.create(kind='article', text_path=path.rsplit('/', 1)[0], path=path, label=label, body=body,
                                   order=order, text_type='law', heading_path=['الباب الأول'] if order == 2 else [],
                                   version_from=date(2013, 2, 1))
    read = settings.CORPUS_DIR / surrogates.FILE
    read.parent.mkdir(parents=True)
    read.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in [
        {'path': '/ma/loi/91-97/art_4', 'version': '2013-02-01', 'prompt': surrogates.PROMPT, 'facts': []},
        {'path': '/ma/loi/91-97/art_1', 'version': '2013-02-01', 'prompt': 's1', 'facts': []}]) + '\n')
    yield
    bm25._shelf_paths.cache_clear()


def reading(cid, params):
    """Haiku's reading of each article it was sent, by its letter; never one whose words say it gets no answer."""
    blocks = [b for b in params['messages'][0]['content'].split('\n\n') if b.startswith('[')]
    return {'articles': [{'key': f'[{b[1]}]', 'context_ar': f' سياق {b[1]} ', 'context_fr': f' contexte {b[1]} ',
                          'searches': SEARCHES, 'concepts': [' الكراء ', '', 'الأجل', 'ج', 'د', 'ه', 'و'], 'role': 'obligation',
                          'facts': [{'kind': 'duration', 'words': '15 يوما'}, {'kind': 'actor', 'words': 'المكتري'}]}
                         for b in blocks if 'بلا جواب' not in b]}


def run(*args) -> str:
    out = StringIO()
    call_command('draft_surrogates', *args, stdout=out)
    return out.getvalue()


def test_the_articles_not_read_yet_go_in_groups_and_come_back_kept(index, settings, monkeypatch):
    sent = claude.install(monkeypatch, settings, settings.CORPUS_DIR, reading)
    said = run('--text', '/ma/loi/91-97', '--show', '1')
    # Articles 1 (an older prompt's reading), 2 and 5, in the text's order; 3 says only it was repealed; 4 is read.
    assert said.startswith('3 articles of 1 texts in 1 requests; worst case $')
    assert said.split('\n---\n')[1] == (
        'Text: قانون الكراء\n\nRegisters, in order: msa, msa, darija, darija, darija_latin, french, english, professional\n\n'
        '[A] - › المادة 1\nيطبق هذا القانون على الكراء.\n\n[B] الباب الأول › المادة 2\nيؤدي المكتري الكراء في أجل أقصاه 15 '
        'يوما.\n\n[C] - › المادة 5\nنص بلا جواب.\n')
    assert sent.requests() == []

    said = run('--write')                                    # the shelf: the code of obligations
    request = sent.requests()[0]['params']
    assert request['messages'][0]['content'].startswith('Text: ظهير ' + 'ع' * 155 + '\n')     # by its title, cut
    assert request['thinking'] == {'type': 'disabled'} and request['max_tokens'] == 800 + 1200
    assert (request['model'], request['system'], request['output_config']['format']['schema']) == (
        surrogates.MODEL, surrogates.SYSTEM, surrogates.SCHEMA)
    kept = surrogates.load()[('/ma/code/doc/art_1', '2013-02-01')]
    assert {k: v for k, v in kept.items() if k not in ('searches', 'facts')} == {
        'path': '/ma/code/doc/art_1', 'text_path': '/ma/code/doc', 'version': '2013-02-01', 'prompt': surrogates.PROMPT,
        'model': surrogates.MODEL, 'context_ar': 'سياق A', 'context_fr': 'contexte A',
        'concepts': ['الكراء', 'الأجل', 'ج', 'د', 'ه'], 'role': 'obligation', 'checked': 'owner-provisional'}
    assert kept['facts'] == [{'kind': 'duration', 'words': '15 يوما'}, {'kind': 'actor', 'words': 'المكتري'}]
    # A blank search dropped; this article has no «2», and copies none of its four words in a row.
    assert [s['q'] for s in kept['searches']] == [s for s in SEARCHES if s.strip()]
    assert said.endswith('1 articles read, 7 searches kept, 1 dropped by the rules, 0 articles without an answer; '
                         'roles: obligation 1\n')

    said = run('--text', '/ma/loi/91-97', '--text', '/ma/code/doc', '--limit', '2', '--write')
    assert len(sent.requests()) == 2 and '[C]' not in sent.requests()[1]['params']['messages'][0]['content']
    kept = surrogates.load()[('/ma/loi/91-97/art_2', '2013-02-01')]
    # Four words in a row of the article, and its number outside the professional register: dropped.
    assert [(s['q'], s['register']) for s in kept['searches']] == [
        ('واش خاصني نخلص الكراء', 'msa'), ('wach khassni nkhalles lkra', 'darija_latin'), ('payer le loyer', 'french'),
        ('pay the rent', 'english'), ('المادة 2 من القانون 91.97', 'professional')]
    assert said.endswith('2 articles read, 12 searches kept, 4 dropped by the rules, 0 articles without an answer; '
                         'roles: obligation 2\n')
    # B15 reads the durations, amounts, rates and ages each article states, as written.
    assert surrogates.facts('/ma/loi/91-97/art_2') == ['15 يوما'] and surrogates.facts('/ma/loi/91-97/art_4') == []

    # The one left has no answer: said, and asked again next time.
    said = run('--text', '/ma/loi/91-97', '--write')
    assert said.startswith('1 articles of 1 texts in 1 requests;')
    assert said.endswith('0 articles read, 0 searches kept, 0 dropped by the rules, 1 articles without an answer; roles: \n')
    assert run('--text', '/ma/loi/91-97').startswith('1 articles of 1 texts')
    # Nothing left: nothing sent.
    assert run('--text', '/ma/code/doc', '--write').startswith('0 articles of 0 texts in 0 requests')
    assert len(sent.requests()) == 3


def test_no_reading_kept_is_no_facts():
    assert surrogates.load() == {} and surrogates.facts('/ma/loi/91-97/art_2') == []
