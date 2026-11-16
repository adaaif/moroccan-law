"""B7 and B25 of the search plan with the model's third-party pieces stood in (model.py): the encoder reads its folder and
gives each text its normalized vector; the model server embeds for every worker; a question's vector is asked of it and
kept a week; `embed_passages` writes each article's passages (its French, B9's context and searches), here or as files
another machine embeds (`embed_files`) and this one loads."""
import json
import socket
import urllib.request
from datetime import date
from io import StringIO
from urllib.error import HTTPError

import numpy as np
import pytest
from django.core.management import call_command

from apps.corpus.models import Text
from apps.search.management.commands import embed_passages
from apps.search.models import SearchEntry, SearchPassage
from apps.search.services import meaning
from apps.search.services.search import bm25
from apps.search.tests.model import DIM, Session, Tokenizer, stored, vector
from apps.translations.models import FrenchArticle

pytestmark = pytest.mark.django_db


def unit(*weights: tuple[int, float]) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    for i, w in weights:
        v[i] += w
    return v / np.linalg.norm(v)


def test_the_encoder_reads_its_folder_and_gives_each_text_its_vector_in_the_order_given(model, monkeypatch):
    enc = meaning.Encoder(threads=3)
    assert Tokenizer.files == [f'{model}/tokenizer.json']
    assert Session.made == [(f'{model}/model.onnx', 3, ['CPUExecutionProvider'])]
    texts = ['الكراء الإفراغ', 'المكتري', 'loyer expulsion الأجير']     # read shortest first, given back in this order
    got = enc.encode(texts)
    assert got.shape == (3, DIM) and got.dtype == np.float32
    assert np.allclose(got, [unit((0, .5), (1, 1), (2, 1)), unit((0, .5), (1, 1)), unit((0, .5), (1, 1), (2, 1), (3, 1))])
    # In padded batches, the padding is masked: the same vectors.
    assert np.allclose(enc.encode(texts, batch=2), got)
    assert enc.encode([]).shape == (0, DIM)
    # A model that gives a vector a token: the start token's is the text's.
    monkeypatch.setattr(Session, 'output', 'last_hidden_state')
    assert np.allclose(meaning.Encoder(folder='/elsewhere').encode(['المكتري']), [unit((0, .5), (1, 1))])
    assert Tokenizer.files[-1] == '/elsewhere/tokenizer.json'


def ask(url: str, body: bytes | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    try:
        answer = urllib.request.urlopen(request, timeout=30)
    except HTTPError as refused:
        answer = refused
    with answer:
        raw = answer.read()
        # Every answer says what it is and how long.
        assert answer.headers['Content-Type'] == 'application/json' and int(answer.headers['Content-Length']) == len(raw)
        return answer.status, json.loads(raw)


def test_the_model_server_embeds_what_it_is_sent_and_refuses_the_rest(served):
    assert served.out.getvalue() == 'meaning model on http://127.0.0.1:0 (2 threads)\n'
    assert Session.made[0][1] == 2
    assert ask(f'{served.url}/health') == (200, {'ok': True})
    assert ask(f'{served.url}/other') == (404, {})
    assert ask(f'{served.url}/other', b'{}') == (404, {})
    status, body = ask(f'{served.url}/embed', json.dumps({'texts': ['المكتري', 'الكراء الإفراغ']}).encode())
    assert status == 200 and isinstance(body['ms'], float)
    assert np.allclose(body['vectors'], [unit((0, .5), (1, 1)), unit((0, .5), (1, 1), (2, 1))], atol=1e-6)
    assert body['vectors'][0][1] == round(float(unit((0, .5), (1, 1))[1]), 6)         # six decimals travel
    # 32 texts at most, each its first 4,000 letters.
    status, body = ask(f'{served.url}/embed', json.dumps({'texts': ['المكتري'] * 40}).encode())
    assert len(body['vectors']) == 32
    Tokenizer.read.clear()
    ask(f'{served.url}/embed', json.dumps({'texts': ['ك' * 5000]}).encode())
    assert Tokenizer.read == ['ك' * 4000]
    refused = (400, {'errors': [{'field': 'texts', 'code': 'invalid'}]})
    for body in (b'{"texts": [', b'{"words": ["x"]}', b'{"texts": 5}'):
        assert ask(f'{served.url}/embed', body) == refused, body


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def test_a_questions_vector_comes_from_the_model_server_and_is_kept_a_week(served, settings):
    got = meaning.embed_query('المكتري')
    assert np.allclose(got, unit((0, .5), (1, 1)), atol=1e-6)
    # The server gone: what was kept answers; a question never asked has no vector, and search goes on without it.
    settings.SEARCH_MODEL_URL = f'http://127.0.0.1:{free_port()}'
    assert meaning.embed_query('المكتري') == got
    assert meaning.embed_query('الإفراغ') is None
    settings.SEARCH_MODEL = 'another-model'           # kept by model: another model's vector is asked again
    assert meaning.embed_query('المكتري') is None


class Down:
    """The cache's server not answering."""

    def get(self, *args):
        raise ConnectionError('cache down')

    set = get


def test_a_cache_down_is_no_reason_to_lose_the_vector(served, monkeypatch):
    monkeypatch.setattr(meaning, 'cache', Down())
    assert np.allclose(meaning.embed_query('الإفراغ'), unit((0, .5), (2, 1)), atol=1e-6)


@pytest.fixture
def index():
    """The index's rows: a law of two articles with its French, a decree of two (an annex), and the code of obligations,
    which is on the shelf (its rows filed among decrees: the shelf takes it whatever its type)."""
    Text.objects.create(akn_uri='/akn/ma/act/code/doc', type='code', number='doc', title_ar='قانون الالتزامات والعقود')
    bm25._shelf_paths.cache_clear()
    rows = [
        ('text', '/ma/loi/67-12', '', {'ar': 'قانون الكراء'}, 'القانون رقم 67.12', 'law', [], '', None),
        ('article', '/ma/loi/67-12', '/ma/loi/67-12/art_1', {}, '', 'law', ['الباب الأول'], 'المادة 1', 'يؤدي المكتري الكراء.'),
        ('article', '/ma/loi/67-12', '/ma/loi/67-12/art_2', {}, '', 'law', ['الباب الأول'], 'المادة 2', 'يمكن الإفراغ بحكم.'),
        ('text', '/ma/decret/2-14-1', '', {}, 'مرسوم رقم 2.14.1 بتحديد الرسوم ' + 'ر' * 200, 'decree', [], '', None),
        ('article', '/ma/decret/2-14-1', '/ma/decret/2-14-1/art_1', {}, '', 'decree', [], 'المادة 1', 'جدول ' * 3000),
        ('article', '/ma/decret/2-14-1', '/ma/decret/2-14-1/art_2', {}, '', 'decree', [], 'المادة 2', 'تحدد الرسوم.'),
        ('text', '/ma/code/doc', '', {'ar': 'ق.ل.ع'}, 'قانون الالتزامات والعقود', 'decree', [], '', None),
        ('article', '/ma/code/doc', '/ma/code/doc/art_1', {}, '', 'decree', [], '', 'الالتزام عقد.'),
    ]
    for kind, text, path, name, title, kind_of, headings, label, body in rows:
        SearchEntry.objects.create(kind=kind, text_path=text, path=path or text, name=name, title=title, text_type=kind_of,
                                   heading_path=headings, label=label, body=body or '', version_from=date(2013, 11, 28),
                                   in_force=text != '/ma/decret/2-14-1', year=2013 if text == '/ma/loi/67-12' else 2014)
    FrenchArticle.objects.create(text_uri='/akn/ma/act/loi/67-12', order=2, label='Article 2', number='2',
                                 body="L'expulsion par jugement.")
    FrenchArticle.objects.create(text_uri='/akn/ma/act/code/doc', order=1, label='Article premier', number='1',
                                 body="L'obligation est un contrat.")
    yield
    bm25._shelf_paths.cache_clear()


def embed(*args) -> str:
    out = StringIO()
    call_command('embed_passages', *args, stdout=out)
    return out.getvalue()


def passages(path: str) -> list[tuple]:
    return list(SearchPassage.objects.filter(path=path).order_by('lang', 'part', 'model').values_list(
        'lang', 'part', 'text_path', 'model', 'version_from', 'in_force', 'text_type', 'year'))


def close(path: str, part: int, lang: str, text: str) -> bool:
    return np.allclose(stored(SearchPassage.objects.get(path=path, part=part, lang=lang, model='bge-m3')), vector(text),
                       atol=1e-3)


class Clock:
    """The machine's clock, a second a reading."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        self.now += 1.0
        return self.now


def test_each_article_is_embedded_once_its_french_its_context_and_its_searches_apart(model, index, settings, monkeypatch):
    # Article 1 is there already for this version; article 2 under an older one is read again, its old rows replaced.
    SearchPassage.objects.create(path='/ma/loi/67-12/art_1', text_path='/ma/loi/67-12', model='bge-m3', part=0, lang='ar',
                                 version_from=date(2013, 11, 28), text_type='law', vector=[1.0] * DIM)
    SearchPassage.objects.create(path='/ma/loi/67-12/art_2', text_path='/ma/loi/67-12', model='bge-m3', part=5, lang='ar',
                                 version_from=date(2010, 1, 1), text_type='law', vector=[1.0] * DIM)
    # The code's article is there under another model only: not done for this one.
    SearchPassage.objects.create(path='/ma/code/doc/art_1', text_path='/ma/code/doc', model='bge-m3-padded', part=0,
                                 lang='ar', version_from=date(2013, 11, 28), text_type='decree', vector=[1.0] * DIM)
    said = embed('--scope', 'shelf', '--threads', '2')
    assert said.startswith('1 articles to embed (1 already), model bge-m3, scope shelf\n') and Session.made[0][1] == 2
    assert passages('/ma/code/doc/art_1') == [
        ('ar', 0, '/ma/code/doc', 'bge-m3', date(2013, 11, 28), True, 'decree', 2014),
        ('ar', 0, '/ma/code/doc', 'bge-m3-padded', date(2013, 11, 28), True, 'decree', None),     # left as it was
        ('fr', 0, '/ma/code/doc', 'bge-m3', date(2013, 11, 28), True, 'decree', 2014)]
    assert close('/ma/code/doc/art_1', 0, 'ar', 'ق.ل.ع › \nالالتزام عقد.')
    assert close('/ma/code/doc/art_1', 0, 'fr', "ق.ل.ع › \nL'obligation est un contrat.")    # by its address's number

    # B9's reading of article 2: its searches as passages of their own (--searches), its context under the header of
    # its Arabic and its French (--context); each only when asked.
    (settings.CORPUS_DIR / 'derived').mkdir()
    (settings.CORPUS_DIR / 'derived' / 'search_surrogates.jsonl').write_text(json.dumps({
        'path': '/ma/loi/67-12/art_2', 'version': '2013-11-28', 'prompt': 's2', 'context_ar': 'سياق الإفراغ',
        'context_fr': "le cas de l'expulsion", 'searches': [{'q': 'واش يقدر يخرجني'}, {'q': 'expulsion loyer'}],
        'concepts': [], 'facts': []}, ensure_ascii=False) + '\n')
    monkeypatch.setattr(embed_passages, 'time', Clock())
    said = embed('--scope', 'core', '--searches')
    assert said.startswith('1 articles to embed (2 already), model bge-m3, scope core\n')
    # 12, 12, 4 and 3 tokens in a second of the clock; the run in two.
    assert said.endswith('1 of 1 articles, 4 passages this chunk; 1.0 articles/s, 31 tokens/s\ndone: 1 articles in 2s\n')
    assert passages('/ma/loi/67-12/art_2') == [
        (lang, part, '/ma/loi/67-12', 'bge-m3', date(2013, 11, 28), True, 'law', 2013)
        for lang, part in (('ar', 0), ('fr', 0), ('q', 0), ('q', 1))]
    head = 'قانون الكراء › الباب الأول › المادة 2'
    assert close('/ma/loi/67-12/art_2', 0, 'ar', f'{head}\nيمكن الإفراغ بحكم.')
    assert close('/ma/loi/67-12/art_2', 0, 'fr', f"{head}\nL'expulsion par jugement.")
    assert close('/ma/loi/67-12/art_2', 0, 'q', 'واش يقدر يخرجني') and close('/ma/loi/67-12/art_2', 1, 'q', 'expulsion loyer')
    SearchPassage.objects.filter(path='/ma/loi/67-12/art_2').delete()
    embed('--scope', 'core', '--context')
    assert [p[:2] for p in passages('/ma/loi/67-12/art_2')] == [('ar', 0), ('fr', 0)]
    assert close('/ma/loi/67-12/art_2', 0, 'ar', f'{head}\nسياق الإفراغ\nيمكن الإفراغ بحكم.')
    assert close('/ma/loi/67-12/art_2', 0, 'fr', f"{head}\nle cas de l'expulsion\nL'expulsion par jugement.")
    assert passages('/ma/loi/67-12/art_1')[0][1] == 0 and SearchPassage.objects.filter(path='/ma/loi/67-12/art_1').count() == 1

    # Every type, a trial of one, an annex read to its first characters; a text with no name is named by its title.
    said = embed('--scope', 'all', '--limit', '1', '--max-chars', '50')
    assert said.startswith('1 articles to embed (3 already), model bge-m3, scope all\n')
    assert passages('/ma/decret/2-14-1/art_1') == [('ar', 0, '/ma/decret/2-14-1', 'bge-m3', date(2013, 11, 28), False, 'decree', 2014)]
    title = ('مرسوم رقم 2.14.1 بتحديد الرسوم ' + 'ر' * 200)[:120]
    assert close('/ma/decret/2-14-1/art_1', 0, 'ar', f'{title} › المادة 1\n' + ' '.join(['جدول'] * 10))
    assert not SearchPassage.objects.filter(path='/ma/decret/2-14-1/art_2').exists()


def test_passages_go_out_as_files_another_machine_embeds_and_come_back_as_rows(model, index, tmp_path):
    folder = tmp_path / 'chunks'
    said = embed('--scope', 'core', '--out', str(folder))
    assert said.startswith('3 articles to embed (0 already)') and 'done: 3 articles in' in said and str(folder) in said
    assert not SearchPassage.objects.exists()
    lines = [json.loads(line) for line in (folder / '00000.jsonl').read_text().splitlines()]
    assert lines[0] == {'path': '/ma/loi/67-12/art_1', 'text_path': '/ma/loi/67-12', 'version_from': '2013-11-28',
                        'in_force': True, 'text_type': 'law', 'year': 2013, 'part': 0, 'lang': 'ar',
                        'text': 'قانون الكراء › الباب الأول › المادة 1\nيؤدي المكتري الكراء.'}
    assert [(x['path'], x['lang']) for x in lines] == [('/ma/loi/67-12/art_1', 'ar'), ('/ma/loi/67-12/art_2', 'ar'),
                                                     ('/ma/loi/67-12/art_2', 'fr'), ('/ma/code/doc/art_1', 'ar'),
                                                     ('/ma/code/doc/art_1', 'fr')]

    out = StringIO()
    call_command('embed_files', str(folder), '--threads', '3', '--model-dir', '/models/bge-m3', stdout=out)
    assert out.getvalue().splitlines()[0] == '1 chunks to embed' and '1 of 1 chunks, 5 passages' in out.getvalue()
    assert Session.made[-1] == ('/models/bge-m3/model.onnx', 3, ['CPUExecutionProvider'])
    vectors = np.load(folder / '00000.npy')
    assert vectors.dtype == np.float16 and vectors.shape == (5, DIM)
    assert np.allclose(vectors[0], vector(lines[0]['text']), atol=1e-3)
    assert not list(folder.glob('*.tmp'))

    # A chunk not embedded yet is left; one that is, loaded.
    (folder / '00001.jsonl').write_text(json.dumps({**lines[0], 'path': '/ma/loi/67-12/art_9', 'version_from': None}) + '\n')
    out = StringIO()
    call_command('embed_passages', '--load', str(folder), stdout=out)
    assert out.getvalue() == '5 passages from 1 of 2 chunks written, model bge-m3\n'
    assert passages('/ma/loi/67-12/art_2') == [
        ('ar', 0, '/ma/loi/67-12', 'bge-m3', date(2013, 11, 28), True, 'law', 2013),
        ('fr', 0, '/ma/loi/67-12', 'bge-m3', date(2013, 11, 28), True, 'law', 2013)]
    assert np.allclose(stored(SearchPassage.objects.get(path='/ma/loi/67-12/art_1')), vectors[0], atol=1e-3)
    # The embedded chunk is not embedded again.
    out = StringIO()
    call_command('embed_files', str(folder), stdout=out)
    assert out.getvalue().splitlines()[0] == '1 chunks to embed' and (folder / '00001.npy').exists()
    # Both chunks embedded now: both loaded, a passage of no known version kept without one.
    out = StringIO()
    call_command('embed_passages', '--load', str(folder), stdout=out)
    assert out.getvalue() == '6 passages from 2 of 2 chunks written, model bge-m3\n'
    assert passages('/ma/loi/67-12/art_9') == [('ar', 0, '/ma/loi/67-12', 'bge-m3', None, True, 'law', 2013)]
