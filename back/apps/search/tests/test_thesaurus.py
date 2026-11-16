"""B10 of the search plan: one thesaurus for the law. Its candidates come from the everyday list, the topics' doors, the
explained concepts and the concepts B9 read three times or more; Haiku's drafts (a stand-in for the API) give each its
people's words; the build grounds each term in the index's counts, keeps a word only one concept claims, and links the
concepts read together. Search reads the sure concepts' words as everyday words when SEARCH_THESAURUS is set."""
import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.corpus.tests import claude
from apps.search.models import SearchEntry
from apps.search.services import index, thesaurus, vocab

pytestmark = pytest.mark.django_db

A, B, C, D = 'عقد الشغل', 'الأجر', 'الفصل التعسفي', 'المحكمة'
SA, SB, SC = 'عقد-الشغل', 'الاجر', 'الفصل-التعسفي'
Z1, Z2, Z3, U = 'ياقوت', 'وشاح', 'زمرد', 'عقيق'      # concepts with no draft (U's word not the index's)
# B9's concepts by article: A read in 21 articles, B in 5, C and D in 4, Z1, Z2, Z3 and U in 3 (each a candidate),
# «نادر» once (not one). A is read with B four times, with C three, with D and each Z twice, with U once; Z1 twice with U.
READ = [[A, B, C], [A, B], [A, B], [A, C], [A, C], [A, D, B], [A, D], [A, Z1, U], [A, Z1], [A, Z2], [A, Z2], [A, Z3],
        [A, Z3], *[[A]] * 8, [B], [C], [D], ['نادر'], [Z1, U], [Z2], [Z3], [U], [D]]
DRAFTS = {
    A: {'fr': 'contrat de travail', 'darija': ['الكونطرا', 'عَقْد الشغل', 'عقد الخدمة', 'الكونطرا ديال الخدمة'],
        'arabizi': ['lkontra', 'l9ard', 'kontra'], 'en': 'employment contract', 'sure': True},
    B: {'fr': '', 'darija': [' الخلصة '], 'arabizi': ['l9ard', 'lkhlsa'], 'en': 'wage', 'sure': False},
    C: {'fr': 'licenciement abusif', 'darija': ['الطرد التعسفي'], 'arabizi': [], 'en': 'ok', 'sure': True},
}


def art(i: int) -> str:
    return f'/ma/loi/65-99/art_{i}'


@pytest.fixture
def sources(tmp_path, monkeypatch):
    """The approved everyday list (one form, one entry with nothing to keep) and what B9 read, under the test's folder."""
    everyday = tmp_path / 'everyday.json'
    everyday.write_text(json.dumps({'entries': [
        {'typed': ['الكونطرا'], 'kind': 'darija', 'means': [A, 'اتفاق الشغل']},
        {'typed': ['x'], 'kind': 'darija', 'means': ['  ', 'ك' * 61, 'ك' * 60, '؟؟؟']},
    ]}, ensure_ascii=False))
    monkeypatch.setattr(vocab, 'FILE', everyday)
    monkeypatch.setattr(thesaurus, 'FILE', tmp_path / 'thesaurus.json')
    vocab.entries.cache_clear()
    (tmp_path / 'derived').mkdir()
    (tmp_path / 'derived' / 'search_surrogates.jsonl').write_text(''.join(
        json.dumps({'path': art(i), 'version': '2004-06-08', 'prompt': 's2', 'concepts': concepts}, ensure_ascii=False) + '\n'
        for i, concepts in enumerate(READ, 1)))
    yield tmp_path
    vocab.entries.cache_clear()
    thesaurus.load.cache_clear()


def drafting(errored: set):
    """The API's answer to a request: each numbered term drafted (the three above as written, the others with nothing),
    with three items no term has; the requests in `errored` not answered."""
    def answer(cid, params):
        if cid in errored:
            return None
        lines = params['messages'][0]['content'].splitlines()
        terms = [{'n': n, **DRAFTS.get(line.split(' ', 1)[1], {'fr': '', 'darija': [], 'arabizi': [], 'en': '', 'sure': True})}
                 for n, line in enumerate(lines, 1)]
        junk = {'fr': 'x', 'darija': [], 'arabizi': [], 'en': 'x', 'sure': True}
        return {'terms': [*terms, {'n': 0, **junk}, {'n': len(lines) + 1, **junk}, {'n': '1', **junk}]}
    return answer


def run(*args) -> str:
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def test_candidates_are_drafted_once_and_a_request_the_api_did_not_answer_is_sent_again(sources, settings, monkeypatch):
    sent = claude.install(monkeypatch, settings, sources, drafting({'th0001'}))
    said = run('draft_thesaurus')
    assert sent.requests() == []                    # nothing is paid without --write
    # Everyday: A, «اتفاق الشغل», sixty letters and «؟؟؟» (a blank meaning and one past 60 letters are no terms); B9: the
    # eight read three times, never «نادر».
    assert 'everyday 4,' in said and 'b9 8' in said
    cands = thesaurus.candidates()
    assert thesaurus.slug('ك' * 60) in cands and thesaurus.slug('ك' * 61) not in cands
    assert (cands[SA], cands[SB]) == ({'ar': A, 'sources': ['everyday', 'b9']}, {'ar': B, 'sources': ['b9']})
    assert cands['المحكمه']['sources'] == ['b9'] and 'نادر' not in cands
    door = next(c for c in cands.values() if 'door' in c['sources'])
    assert door['sources'].count('door') == 1        # a phrase many door words mean is one candidate, said once
    assert 'explained' in cands['النفقه']['sources']

    run('draft_thesaurus', '--write')
    first = sent.requests()
    assert [r['custom_id'] for r in first] == [f'th{i:04d}' for i in range(len(first))]
    terms = [line.split(' ', 1)[1] for r in first for line in r['params']['messages'][0]['content'].splitlines()]
    assert terms == [c['ar'] for c in cands.values()]
    assert [len(r['params']['messages'][0]['content'].splitlines()) for r in first[:2]] == [40, 40]
    params = first[0]['params']
    assert (params['model'], params['max_tokens'], params['system']) == (thesaurus.MODEL, 600 * 40, thesaurus.SYSTEM)
    assert params['output_config']['format']['schema'] == thesaurus.SCHEMA
    assert first[0]['params']['messages'][0]['content'].splitlines()[0] == f'1 {A}'
    kept = json.loads((sources / thesaurus.DRAFTS).read_text())
    assert kept['model'] == thesaurus.MODEL
    assert kept['drafts'][SA] == DRAFTS[A] and kept['drafts'][SB] == DRAFTS[B]
    missed = terms[40:80]                           # the second request errored: its terms have no draft
    assert len(kept['drafts']) == len(terms) - 40 and not {thesaurus.slug(t) for t in missed} & set(kept['drafts'])

    said = run('draft_thesaurus', '--write')
    again = sent.requests()[len(first):]
    assert [line.split(' ', 1)[1] for r in again for line in r['params']['messages'][0]['content'].splitlines()] == missed
    assert f'{len(terms)} drafts kept' in said
    assert len(json.loads((sources / thesaurus.DRAFTS).read_text())['drafts']) == len(terms)
    # All drafted: nothing to send.
    run('draft_thesaurus', '--write')
    assert len(sent.requests()) == len(first) + len(again)


def test_the_thesaurus_keeps_grounded_concepts_their_own_words_and_the_concepts_read_with_them(sources, settings):
    (sources / thesaurus.DRAFTS).parent.mkdir(parents=True)
    (sources / thesaurus.DRAFTS).write_text(json.dumps({'drafts': {thesaurus.slug(k): v for k, v in DRAFTS.items()}},
                                                       ensure_ascii=False))
    # The index's counts: every word of A, B, C and the Zs (not D's, U's, nor «؟؟؟», which has none); «خدم» as often as
    # the law's own words, «طرد» less.
    counts = {'عقد': 30, 'شغل': 30, 'اجر': 30, 'فصل': 30, 'تعسف': 30, 'خدم': thesaurus.LAW_WORD, 'طرد': thesaurus.LAW_WORD - 1,
              'contrat': 500, 'travail': 500, 'ياقوت': 3, 'شاح': 3, 'زمرد': 3}
    (sources / index.TERMS).write_text(json.dumps(counts, ensure_ascii=False))
    defining = 'يقصد بما يلي في هذا الباب: عقد الشغل هو الاتفاق الذي يلتزم بموجبه الأجير.'
    for i in range(1, 7):
        SearchEntry.objects.create(kind='article', text_path='/ma/loi/65-99', path=art(100 + i), text_type='law', body=defining)
    SearchEntry.objects.create(kind='article', text_path='/ma/loi/65-99', path=art(200), text_type='law',
                               body='يراد بالأجر في هذا القانون: الأجر هو المقابل.')
    SearchEntry.objects.create(kind='article', text_path='/ma/loi/65-99', path=art(201), text_type='law',
                               body='يقصد ب' + 'كلام ' * 70 + 'عقد الشغل')                 # past its first 300 letters
    SearchEntry.objects.create(kind='article', text_path='/ma/loi/65-99', path=art(202), text_type='law',
                               body='ينتهي عقد الشغل بانتهاء مدته.')                    # not a definition
    SearchEntry.objects.create(kind='text', text_path='/ma/loi/65-99', path='/ma/loi/65-99', text_type='law',
                               body=defining)                                           # a title row
    assert thesaurus.load() == {}                   # none yet; the build's is read at once
    said = run('build_thesaurus')
    assert said.strip() == ("6 concepts written (2 with a defining article, 6 with related ones); people's words: "
                            "{'darija': 4, 'arabizi': 2, 'fr': 2, 'en': 2}")
    data = json.loads(thesaurus.FILE.read_text())
    assert data['checked'] == 'owner-provisional' and set(data) == {'about', 'date', 'checked', 'concepts'}
    concepts = data['concepts']
    assert set(concepts) == {SA, SB, SC, Z1, Z2, Z3}  # D's and U's words are not the index's
    # «l9ard» is claimed by A and B: left to neither. Words cut to three and two, the term itself and two letters left out.
    assert concepts[SA] == {
        'ar': A, 'darija': ['الكونطرا', 'عقد الخدمة'], 'arabizi': ['lkontra'], 'fr': ['contrat de travail'],
        'en': ['employment contract'], 'sure': True, 'sources': ['everyday', 'b9'],
        'related': [SB, SC, Z1, Z2],                 # by how much more often than by chance; four at most (Z3 next)
        'defines': [art(101), art(102), art(103), art(104), art(105)], 'about': [art(i) for i in range(1, 21)]}
    assert concepts[SB] == {'ar': B, 'darija': ['الخلصة'], 'arabizi': ['lkhlsa'], 'fr': [], 'en': ['wage'], 'sure': False,
                            'sources': ['b9'], 'related': [SA], 'defines': [art(200)], 'about': [art(i) for i in (1, 2, 3, 6, 22)]}
    assert concepts[SC] == {'ar': C, 'darija': ['الطرد التعسفي'], 'arabizi': [], 'fr': ['licenciement abusif'], 'en': [],
                            'sure': True, 'sources': ['b9'], 'related': [SA], 'defines': [], 'about': [art(i) for i in (1, 4, 5, 23)]}
    # No draft: no people's words, sure; Z1 is read with U more than with A, and U is not kept.
    for z, rows in ((Z1, (8, 9, 26)), (Z2, (10, 11, 27)), (Z3, (12, 13, 28))):
        assert concepts[z] == {'ar': z, 'darija': [], 'arabizi': [], 'fr': [], 'en': [], 'sure': True, 'sources': ['b9'],
                               'related': [SA], 'defines': [], 'about': [art(i) for i in rows]}, z

    # The people's words search reads: the sure concepts' (not B's), never an Arabic word the law itself writes 20
    # times or more («عقد الخدمة»), always a word in Latin letters.
    assert thesaurus.people_words() == [('الكونطرا', [A]), ('lkontra', [A]), ('contrat de travail', [A]),
                                        ('employment contract', [A]), ('الطرد التعسفي', [C]), ('licenciement abusif', [C])]
    assert ('lkontra', [A]) not in vocab.entries()
    settings.SEARCH_THESAURUS = True
    vocab.entries.cache_clear()
    entries = vocab.entries()
    assert ('lkontra', [A]) in entries and ('employment contract', [A]) in entries
    # The approved list wins on a word both hold.
    assert [means for typed, means in entries if typed == 'الكونطرا'] == [[A, 'اتفاق الشغل']]
    assert vocab.rewrites('lkontra') == [A]


def test_no_thesaurus_file_is_an_empty_thesaurus(tmp_path, monkeypatch):
    monkeypatch.setattr(thesaurus, 'FILE', tmp_path / 'none.json')
    thesaurus.load.cache_clear()
    try:
        assert thesaurus.load() == {} and thesaurus.people_words() == []
    finally:
        thesaurus.load.cache_clear()
