"""B1 of the search plan: the test set drafted from articles drawn at random by stratum (laws, decrees, orders), the formal
and short ones left out, a register each in turn; each article goes to Haiku (a stand-in for the API) with its text, its
headings and its official French; the usable questions are written once, marked owner-provisional."""
import json
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.models import Article, Consolidation, Status, Text, Version
from apps.corpus.services.codes import display_name
from apps.corpus.tests import claude
from apps.search.management.commands import draft_test_questions
from apps.search.services import testset
from apps.search.services.index import rebuild
from apps.translations.models import FrenchArticle

pytestmark = pytest.mark.django_db

LONG = ' وتطبق أحكام هذا الباب على جميع العقود المبرمة بعد دخوله حيز التنفيذ دون استثناء.' * 3       # 240 letters


def text(uri, kind, bodies, **more):
    number = uri.rsplit('/', 1)[1]
    t = Text.objects.create(akn_uri=uri, type=kind, number=number, title_ar=f'نص رقم {number} ' + 'ع' * 400, **more)
    v = Version.objects.create(text=t, language='ar', valid_from=date(2015, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    for n, body in enumerate(bodies, 1):
        Article.objects.create(version=v, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}', body=body,
                               heading_path=['الباب الأول'] if n == 1 else [])
    return t


@pytest.fixture
def corpus():
    # A law of four articles (one only publishes it, one too short, one long that says «ينشر هذا» in passing), two
    # decrees, an order, and a repealed law.
    text('/akn/ma/act/loi/91-97', 'law', ['يؤدي المكتري الكراء.' + LONG, 'ينشر هذا القانون بالجريدة الرسمية.' + LONG,
                                          'قصير.', 'يمكن الإفراغ بحكم ينشر هذا الحكم.' + LONG + 'ك' * 4000])
    text('/akn/ma/act/decret/2-91-1', 'decree', ['تحدد الرسوم.' + LONG, 'تؤدى الرسوم.' + LONG])
    text('/akn/ma/act/arrete/1-91', 'order', ['يحدد النموذج.' + LONG])
    text('/akn/ma/act/loi/92-97', 'law', ['نص منسوخ.' + LONG], status=Status.REPEALED)
    FrenchArticle.objects.create(text_uri='/akn/ma/act/loi/91-97', order=1, label='Article premier', number='1',
                                 body='Le locataire paie le loyer. ' + 'x' * 2000)
    rebuild(log=lambda m: None)


def test_articles_are_drawn_by_stratum_without_the_formal_short_or_repealed_ones(corpus):
    items = testset.sample(4, seed=26)
    assert items == testset.sample(4, seed=26) and len(items) == 4       # the same draw for the same seed
    paths = [i['path'] for i in items]
    # Two laws drawn (half of four, a quarter more, rounded), two decrees, one order; four kept, in a drawn order.
    assert paths == ['/ma/decret/2-91-1/art_2', '/ma/loi/91-97/art_1', '/ma/decret/2-91-1/art_1', '/ma/arrete/1-91/art_1']
    assert [i['id'] for i in items] == ['q0000', 'q0001', 'q0002', 'q0003']
    assert [i['register'] for i in items] == ['msa', 'darija', 'darija_latin', 'french']
    for item in items:
        assert item['text_path'] == item['path'].rsplit('/', 1)[0] and item['article'].eid == item['path'].rsplit('/', 1)[1]
        assert item['text'].akn_uri.replace('/akn/ma/act', '/ma') == item['text_path']
        assert item['french'] == ('Le locataire paie le loyer. ' + 'x' * 2000 if item['path'] == '/ma/loi/91-97/art_1' else '')
    # Every article that can be asked about, at most n: never the short one, the repealed text's, or the one that only
    # says the law is published.
    assert sorted(i['path'] for i in testset.sample(10, seed=1)) == [
        '/ma/arrete/1-91/art_1', '/ma/decret/2-91-1/art_1', '/ma/decret/2-91-1/art_2', '/ma/loi/91-97/art_1',
        '/ma/loi/91-97/art_4']


def test_an_articles_request_names_its_register_its_text_headings_and_french(corpus):
    item = next(i for i in testset.sample(6, seed=3) if i['path'] == '/ma/loi/91-97/art_1')
    content = testset.content({**item, 'register': 'professional'})
    parts = content.split('\n\n')
    description, example = testset.REGISTERS['professional']
    assert parts[0] == f'Register: professional: {description}. For example: {example}'
    assert parts[1] == f"Text: {display_name(item['text'])['ar']} ({('نص رقم 91-97 ' + 'ع' * 400)[:300]})"
    assert parts[2] == 'Headings: الباب الأول'
    assert parts[3] == 'Article: المادة 1\n' + ('يؤدي المكتري الكراء.' + LONG)
    assert parts[4] == 'Official French: ' + ('Le locataire paie le loyer. ' + 'x' * 2000)[:testset.FRENCH_MAX]
    other = next(i for i in testset.sample(6, seed=3) if i['path'] == '/ma/loi/91-97/art_4')
    parts = testset.content(other).split('\n\n')
    assert parts[2] == 'Headings: -' and len(parts) == 4                 # no French: no line for it
    assert parts[3] == 'Article: المادة 4\n' + ('يمكن الإفراغ بحكم ينشر هذا الحكم.' + LONG + 'ك' * 4000)[:testset.BODY_MAX]
    req = testset.requests([other])[0]
    assert req['custom_id'] == other['id'] and req['params']['max_tokens'] == 1500
    assert req['params']['model'] == testset.MODEL and req['params']['messages'][0]['content'] == testset.content(other)
    assert req['params']['system'] == testset.SYSTEM and req['params']['output_config']['format']['schema'] == testset.SCHEMA


QUESTION = ' '.join(['كلمة'] * 24 + ['الكراء؟'])        # 25 words: the most a question may have


def asking(cid, params):
    """Haiku's answers: a usable question of 25 words, one of 26, one it says is not usable, one usable with no words, and
    none for the last request."""
    return {'q0000': {'usable': True, 'question': f'  {QUESTION} ', 'intent': 'question', 'why': 'rent'},
            'q0001': {'usable': True, 'question': ' '.join(['كلمة'] * 26), 'intent': 'words', 'why': 'x'},
            'q0002': {'usable': False, 'question': 'سؤال عن النموذج', 'intent': 'words', 'why': 'formal'},
            'q0003': {'usable': True, 'question': '   ', 'intent': 'words', 'why': 'x'}}.get(cid)


def test_the_test_set_is_drafted_once_with_the_usable_questions(corpus, monkeypatch, settings, tmp_path):
    target = tmp_path / 'test.json'
    monkeypatch.setattr(draft_test_questions, 'TEST', target)
    sent = claude.install(monkeypatch, settings, tmp_path, asking)
    out = StringIO()
    call_command('draft_test_questions', '--n', '5', '--seed', '26', '--show', '1', stdout=out)
    said = out.getvalue()
    assert said.startswith('5 articles: ') and '\nregisters: msa 1, darija 1, darija_latin 1, french 1, english 1\n' in said
    assert '\n--- q0000 ' in said and '\n--- q0001 ' not in said and sent.requests() == []
    out = StringIO()
    call_command('draft_test_questions', '--n', '5', '--seed', '26', '--write', stdout=out)
    assert [r['custom_id'] for r in sent.requests()] == ['q0000', 'q0001', 'q0002', 'q0003', 'q0004']
    data = json.loads(target.read_text())
    first = testset.sample(5, seed=26)[0]
    assert data['questions'] == [{
        'q': QUESTION, 'expect': [first['path']], 'register': 'msa', 'intent': 'question', 'why': 'rent',
        'text_type': first['text'].type, 'checked': 'owner-provisional', 'drafted_by': testset.MODEL, 'prompt': testset.PROMPT}]
    assert '(seed 26;' in data['about']
    assert out.getvalue().endswith(f"1 questions written to {target}; fell out: {{'not usable': 2, 'no answer': 1, 'too long': 1}}\n")
    # Drafted once: never again over it.
    with pytest.raises(CommandError, match=r'test\.json exists'):
        call_command('draft_test_questions', '--n', '4', '--write', stdout=StringIO())
    assert len(sent.requests()) == 5


def sized(start: str, n: int) -> str:
    return start + ' ' + 'ع' * (n - len(start) - 1)


def test_the_lines_between_an_article_drawn_and_one_left():
    # 150 letters is long enough, 149 not; a text that publishes the law is left under 400 letters, drawn from 400.
    text('/akn/ma/act/loi/93-97', 'law', [sized('نص المادة.', 150), sized('نص المادة.', 149),
                                          sized('ينشر هذا القانون بالجريدة الرسمية.', 399),
                                          sized('ينشر هذا القانون بالجريدة الرسمية.', 400)])
    order = Text.objects.create(akn_uri='/akn/ma/act/arrete/2-91', type='order', number='2-91', title_ar='قرار')
    v = Version.objects.create(text=order, language='ar', valid_from=date(2015, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='فصل فريد', number='1', eid='art_1', body='يحدد النموذج.' + LONG)
    FrenchArticle.objects.create(text_uri=order.akn_uri, order=1, label='Article unique', number='1', body='Le modèle est fixé.')
    rebuild(log=lambda m: None)
    items = {i['path']: i for i in testset.sample(10, seed=1)}
    assert sorted(items) == ['/ma/arrete/2-91/art_1', '/ma/loi/93-97/art_1', '/ma/loi/93-97/art_4']
    assert items['/ma/arrete/2-91/art_1']['french'] == 'Le modèle est fixé.'      # by its number: its label has none


def test_a_draw_gives_as_many_articles_as_asked_when_more_could_be_asked_about():
    # Three asked: two laws, a decree and an order drawn (a quarter more, for the formal ones that fall out), none falls
    # out here, and three come back.
    text('/akn/ma/act/loi/94-97', 'law', ['أ.' + LONG, 'ب.' + LONG, 'ج.' + LONG])
    text('/akn/ma/act/decret/2-94-1', 'decree', ['د.' + LONG, 'ه.' + LONG])
    text('/akn/ma/act/arrete/3-94', 'order', ['و.' + LONG, 'ز.' + LONG])
    rebuild(log=lambda m: None)
    assert [i['path'] for i in testset.sample(3, seed=2)] == ['/ma/loi/94-97/art_2', '/ma/arrete/3-94/art_1',
                                                              '/ma/decret/2-94-1/art_2']
