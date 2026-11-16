"""B2 of the search plan without a search: the pairs to grade (what a search showed, the articles a set expects, other
variants' answers) go to the judge 24 a request, each article under its text's name, headings and label; the grades come
back by number and are kept by question, address and version; the judge is checked against the expected articles and
the unrelated ones slipped in."""
import json
from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.search.services import judge

pytestmark = pytest.mark.django_db

Q = 'واش يقدر مول الدار يخرجني'
VERSION = '2013-02-01:as_published'


def art(n: int) -> str:
    return f'/ma/loi/91-97/art_{n}'


@pytest.fixture
def law():
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/91-97', type='law', number='91-97', number_as_printed='91.97',
                               title_ar='القانون رقم 91.97 المتعلق بعقود الكراء')
    old = Version.objects.create(text=text, language='ar', valid_from=date(2010, 2, 1), consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=old, order=1, label='المادة 1', number='1', eid='art_1', body='نص قديم.')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2013, 2, 1), consolidation=Consolidation.AS_PUBLISHED)
    for n in range(1, 27):
        Article.objects.create(version=v, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                               heading_path=['الباب الأول', 'الإفراغ'] if n == 26 else [],
                               body='يمكن الإفراغ بحكم. ' * 100 if n == 26 else f'نص المادة {n}.')
    return text


def test_the_pairs_not_graded_yet_go_to_the_judge_24_a_request(law):
    rows = [{'q': Q, 'expect': [art(1), 'missing:family', '/ma/loi/91-97'], 'shown': [art(n) for n in range(2, 26)]},
            {'q': Q, 'expect': art(3), 'shown': [art(2)]},          # the same question in another set: one pool
            {'q': 'سؤال آخر', 'expect': 'missing:family'}]
    pool = judge.pools(rows, {Q: [art(26), art(2), '/ma/loi/1-01/art_1']})
    # What was shown, the expected articles (never a text or a code not held here), the other variants', each once.
    assert pool == {Q: [*(art(n) for n in range(2, 26)), art(1), art(26), '/ma/loi/1-01/art_1'], 'سؤال آخر': []}
    known = {judge.key(Q, art(2), VERSION): {'grade': 1}, judge.key(Q, art(4), '2010-02-01:as_published'): {'grade': 3}}
    reqs, meta = judge.requests(pool, known)
    # art 2 graded on this version: left; art 4 graded on another version: again; an address the site lacks: never.
    assert [r['custom_id'] for r in reqs] == ['g00000-0', 'g00000-1']
    todo = [art(n) for n in range(3, 26)] + [art(1), art(26)]
    assert meta == {'g00000-0': (Q, [(p, VERSION) for p in todo[:24]]), 'g00000-1': (Q, [(p, VERSION) for p in todo[24:]])}
    first = reqs[0]['params']
    assert (first['model'], first['max_tokens'], first['system']) == (judge.MODEL, 3000, judge.SYSTEM)
    assert first['output_config']['format']['schema'] == judge.SCHEMA
    blocks = first['messages'][0]['content'].split('\n\n')
    assert blocks[0] == f'Search: {Q}' and blocks[1] == '[1] القانون رقم 91.97 المتعلق بعقود الكراء ›  › المادة 3\nنص المادة 3.'
    last = reqs[1]['params']['messages'][0]['content'].split('\n\n')
    body = 'يمكن الإفراغ بحكم. ' * 100
    assert last == [f'Search: {Q}',
                    f'[1] القانون رقم 91.97 المتعلق بعقود الكراء › الباب الأول › الإفراغ › المادة 26\n{body[:judge.BODY_MAX]}']


def test_grades_come_back_by_number_and_are_kept_by_question_address_and_version(tmp_path):
    meta = {'g00000-0': (Q, [(art(1), VERSION), (art(2), VERSION)]), 'g00001-0': ('سؤال', [(art(3), VERSION)])}
    results = {'g00000-0': {'data': {'grades': [{'n': 2, 'grade': 0, 'why': 'unrelated'}, {'n': 1, 'grade': 3},
                                                 {'n': 3, 'grade': 2, 'why': 'x'}, {'n': 1, 'grade': 4, 'why': 'x'},
                                                 {'n': '1', 'grade': 2, 'why': 'x'}]}},
               'g00001-0': {'data': None, 'error': 'errored'}}
    rows = judge.collect(results, meta)
    assert [(r['q'], r['path'], r['version'], r['grade'], r['why'], r['judge'], r['prompt']) for r in rows] == [
        (Q, art(2), VERSION, 0, 'unrelated', judge.MODEL, judge.PROMPT), (Q, art(1), VERSION, 3, '', judge.MODEL, judge.PROMPT)]
    assert all(len(r['at']) == 19 for r in rows)            # to the second
    assert judge.load() == {}
    judge.save(rows)
    judge.save([{**rows[1], 'grade': 2, 'why': 'again'}])  # a later grade of the same pair wins
    (tmp_path / judge.FILE).write_text((tmp_path / judge.FILE).read_text() + '\n')
    known = judge.load()
    assert {k: v['grade'] for k, v in known.items()} == {(Q, art(2), VERSION): 0, (Q, art(1), VERSION): 2}
    assert judge.by_question(known) == {Q: {art(2): 0, art(1): 2}}


def test_the_judge_is_checked_against_the_expected_and_the_unrelated_articles(settings):
    other = 'لم يقيم'
    known = {judge.key(Q, art(1), VERSION): {'grade': 3}, judge.key(Q, art(2), VERSION): {'grade': 1},
             judge.key(Q, art(7), VERSION): {'grade': 0}, judge.key(Q, art(8), VERSION): {'grade': 1},
             judge.key(Q, art(9), VERSION): {'grade': 2}, judge.key(other, art(1), VERSION): {'grade': 2}}
    # Expected: art. 1 graded 3, art. 9 graded 2 (both count), art. 2 graded 1 (does not), art. 5 never graded; the
    # other question's art. 1 graded 2 under it.
    rows = [{'q': Q, 'expect': [art(1), art(2), art(9), art(5)]}, {'q': other, 'expect': art(1)},
            {'q': 'سؤال لم يقيم', 'expect': art(1)}]
    assert judge.checks(rows, known) == {'expected_graded': 4, 'expected_2_or_3': 3, 'expected_share': 0.75,
                                         'unrelated_graded': 0, 'unrelated_0': 0, 'unrelated_0_or_1': 0}
    planted = settings.CORPUS_DIR / judge.NEGATIVES
    planted.parent.mkdir(parents=True)
    planted.write_text(json.dumps({Q: [art(7), art(8), art(9), art(10)], other: [art(1), art(7)]}, ensure_ascii=False))
    # Graded: 0, 1 and 2 for the first question, 2 for the other's (its art. 7 never graded under it).
    assert judge.checks(rows, known) == {'expected_graded': 4, 'expected_2_or_3': 3, 'expected_share': 0.75,
                                         'unrelated_graded': 4, 'unrelated_0': 1, 'unrelated_0_or_1': 2}
    assert judge.checks([{'q': 'سؤال لم يقيم', 'expect': art(1)}], known)['expected_share'] is None


def test_unrelated_articles_are_drawn_from_other_sets_and_kept(settings):
    rows = [{'q': 'a', 'set': 'housing', 'shown': ['/h/1', '/h/2']}, {'q': 'b', 'set': 'housing', 'shown': ['/h/3']},
            {'q': 'c', 'set': 'work', 'shown': ['/w/1']}, {'q': 'd', 'set': 'work', 'shown': []},
            {'q': 'e', 'set': 'road', 'shown': ['/r/1']}]
    out = judge.negatives(rows, 2, seed=7)
    assert out == judge.negatives(rows, 2, seed=7)          # the same draw for the same seed
    assert len(out) == 2
    for q, paths in out.items():
        own = next(r['set'] for r in rows if r['q'] == q)
        assert len(paths) == 2 and all(p.split('/')[1][0] != own[0] for p in paths)
    assert set(judge.negatives(rows, 5, seed=1)) == {'a', 'b', 'c', 'd', 'e'}     # every set has two others to draw from
    path = settings.CORPUS_DIR / judge.NEGATIVES
    path.write_text(json.dumps(out))                        # the first draw alone, as kept
    # A second draw of other questions (more asked than there are) is added to what was kept, which stays as it was.
    more = judge.negatives([{'q': 'f', 'set': 'x', 'shown': ['/x/1']}, {'q': 'g', 'set': 'y', 'shown': ['/y/1']},
                            {'q': 'h', 'set': 'z', 'shown': ['/z/1']}], 10)
    assert set(more) == {'f', 'g', 'h'}
    assert json.loads(path.read_text()) == {**out, **more}
    # A question with one other set only, or none, has no unrelated articles.
    assert judge.negatives([{'q': 'i', 'set': 'x', 'shown': ['/x/1']}, {'q': 'j', 'set': 'y', 'shown': ['/y/1']}], 2) == {}
    assert judge.negatives([{'q': 'a', 'set': 'x', 'shown': ['/x/1']}, {'q': 'b', 'set': 'x', 'shown': ['/x/2']}], 2) == {}
    assert json.loads(path.read_text()) == {**out, **more}


def test_grading_asks_which_questions():
    with pytest.raises(CommandError, match='--tuning or --test'):
        call_command('grade_answers')


def test_grading_sends_nothing_without_write_and_spends_once_with_it(law, settings, monkeypatch, tmp_path):
    """The judge is paid: without --write the pairs waiting and the worst case are said, and nothing reaches the API, no
    ledger line, no grade. A citation is searched without the index's words, so this runs on any database."""
    from io import StringIO

    from apps.corpus.tests import claude
    from apps.search.management.commands import grade_answers
    from apps.search.services import goldset
    from apps.sources.services.ocr.ledger import ledger_path

    folder = tmp_path / 'goldset'
    folder.mkdir()
    (folder / 'mine.json').write_text(json.dumps({'questions': [
        {'q': 'المادة 2 من القانون رقم 91.97', 'expect': art(2)}]}, ensure_ascii=False))
    monkeypatch.setattr(goldset, 'DIR', folder)
    for module in (goldset, grade_answers):
        monkeypatch.setattr(module, 'TEST', folder / 'test.json')
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: {'grades': [{'n': 1, 'grade': 3, 'why': 'x'}]})

    def run(*args):
        out = StringIO()
        call_command('grade_answers', '--tuning', *args, stdout=out)
        return out.getvalue().splitlines()

    said = run()
    assert said[0].startswith('1 questions, 1 pairs to grade in 1 requests; worst case $0.')
    assert sent.requests() == [] and not ledger_path().exists() and not (tmp_path / judge.FILE).exists()
    assert said[1:] == ["graded measures: {'questions': 0, 'ndcg10': 0.0, 'mrr': 0.0, 'recall20': 0.0}",
                        'judge checks (provisional, until lawyers calibrate it): {\'expected_graded\': 0, '
                        "'expected_2_or_3': 0, 'expected_share': None, 'unrelated_graded': 0, 'unrelated_0': 0, "
                        "'unrelated_0_or_1': 0}"]
    said = run('--write')
    params = sent.requests()[0]['params']
    # The worst case said is the request's: a token a character in, its ceiling out, at Haiku's batch prices.
    chars = len(params['system']) + len(params['messages'][0]['content'])
    assert said[0].endswith(f'worst case ${round((chars * 0.10 + 3000 * 0.50) * 0.5 / 1e6, 4)}')
    assert len(sent.requests()) == 1 and ledger_path().exists()
    assert [(r['q'], r['path'], r['grade']) for r in map(json.loads, (tmp_path / judge.FILE).read_text().splitlines())] == [
        ('المادة 2 من القانون رقم 91.97', art(2), 3)]
    assert '1 of 1 pairs graded' in said
    # Graded already: with --write, nothing more to send.
    assert run('--write')[0] == '1 questions, 0 pairs to grade in 0 requests; worst case $0' and len(sent.requests()) == 1
