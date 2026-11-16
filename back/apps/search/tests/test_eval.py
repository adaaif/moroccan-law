"""The search measured (B1, B2 of the search plan) on ParadeDB: each question of a set searched as a reader would, counted
in the top 3 and first (a citation card, a code not held here said, a door that leads to the expected article), by register
and intent; `search_eval` says it and keeps it, `grade_answers` has the judge (a stand-in for the API) grade what search
showed and prints the graded measures. The sets here are the test's own, under its folder."""
import json
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.tests import claude
from apps.search.management.commands import grade_answers, search_eval
from apps.search.services import goldset, judge
from apps.search.services.index import rebuild
from apps.sources.models import Edition, Issue

pytestmark = [pytest.mark.django_db,
              pytest.mark.skipif(connection.vendor != 'postgresql', reason='BM25 needs ParadeDB (TEST_DATABASE_URL)')]

MINE = [
    {'q': 'الإفراغ', 'expect': '/ma/loi/91-97/art_2'},                                  # first
    {'q': 'القانون رقم 91.97', 'expect': ['/ma/loi/91-97'], 'register': 'professional'},   # the citation card
    {'q': 'مدونة الأسرة', 'expect': 'missing:family'},                                   # a code not held here, said
    {'q': 'شدني الرادار', 'expect': '/ma/loi/52-05/art_141', 'lang': 'darija'},          # by the road's radar door
    {'q': 'ج.ر 7533', 'expect': '/bo/general_ar/7533'},                                  # an issue
    {'q': 'تأشيرة الدخول', 'expect': '/ma/loi/91-97/art_1', 'intent': 'question', 'note': 'not in the law'},
    {'q': 'إفراغ', 'expect': '/ma/loi/91-97/art_3'},                                     # in the top 3, not first
]


@pytest.fixture
def sets(tmp_path, settings, monkeypatch):
    """A lease law of three articles and an issue; three sets of the test's own (and its test set) as the only ones."""
    settings.SHOW_DRAFTS = True                 # the doors are drafts while developing
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10))
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/91-97', type='law', number='91-97', number_as_printed='91.97',
                               title_ar='القانون رقم 91.97 المتعلق بعقود الكراء', first_published_in=issue)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2013, 2, 1), consolidation=Consolidation.AS_PUBLISHED)
    for n, body in enumerate(['يؤدي المكتري الكراء في أجله.', 'يمكن الإفراغ بحكم.',
                              'يتم الإفراغ داخل مدة ثلاثة أشهر من تاريخ الإنذار.'], 1):
        Article.objects.create(version=v, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}', body=body)
    penal = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-59-413', type='dahir', number='1-59-413', status='in_force',
                                title_ar='ظهير شريف بالمصادقة على مجموعة القانون الجنائي')
    v = Version.objects.create(text=penal, language='ar', valid_from=date(1962, 6, 5), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='الفصل 490', number='490', eid='art_490', body='نص الفصل.')
    fees = Text.objects.create(akn_uri='/akn/ma/act/loi/95-97', type='law', number='95-97', title_ar='قانون الرسوم')
    v = Version.objects.create(text=fees, language='ar', valid_from=date(2020, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة 1', number='1', eid='art_1', body='490 درهما و490 درهما و490 درهما.')
    rebuild(log=lambda m: None)
    folder = tmp_path / 'goldset'
    folder.mkdir()
    for name, questions in (('mine', MINE), ('other', [{'q': 'الكراء', 'expect': '/ma/loi/91-97/art_1'},
                                                       {'q': 'المكتري', 'expect': '/ma/loi/91-97/art_1'}]),
                            ('test', [{'q': 'الكراء في أجله', 'expect': ['/ma/loi/91-97/art_1']}])):
        (folder / f'{name}.json').write_text(json.dumps({'questions': questions}, ensure_ascii=False))
    for module in (goldset, search_eval):
        monkeypatch.setattr(module, 'DIR', folder)
    for module in (goldset, search_eval, grade_answers):
        monkeypatch.setattr(module, 'TEST', folder / 'test.json')
    return folder


def run(*args) -> str:
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def test_each_question_is_counted_in_the_top_3_first_or_by_a_door(sets):
    result = goldset.evaluate(sets / 'mine.json')
    assert (result['questions'], result['hits'], result['rate'], result['first'], result['by_door']) == (7, 6, 0.857, 5, 1)
    rows = {r['q']: r for r in result['rows']}
    assert [(r['hit'], r['first'], r['by_door']) for r in result['rows']] == [
        (True, True, False), (True, True, False), (True, True, False), (True, True, True), (True, True, False),
        (False, False, False), (True, False, False)]
    assert rows['الإفراغ']['top'] == ['/ma/loi/91-97', '/ma/loi/91-97/art_2', '/ma/loi/91-97/art_3']
    assert rows['الإفراغ']['shown'] == ['/ma/loi/91-97/art_2', '/ma/loi/91-97/art_3']
    assert rows['القانون رقم 91.97']['top'][0] == '/ma/loi/91-97' and rows['ج.ر 7533']['top'] == ['/bo/general_ar/7533']
    assert [(r['register'], r['intent']) for r in result['rows']] == [
        ('msa', 'words'), ('professional', 'citation'), ('msa', 'name'), ('darija', 'words'), ('msa', 'citation'),
        ('msa', 'question'), ('msa', 'words')]
    assert {r['split'] for r in result['rows']} <= {'tune', 'dev'} and rows['الإفراغ']['understood_as'] == 'words'
    assert rows['تأشيرة الدخول']['note'] == 'not in the law'          # the set's own fields kept
    # One split alone: the others' questions are not searched.
    dev = goldset.evaluate(sets / 'mine.json', split='dev')['rows']
    tune = goldset.evaluate(sets / 'mine.json', split='tune')['rows']
    assert sorted(r['q'] for r in dev + tune) == sorted(q['q'] for q in MINE) and {r['split'] for r in dev} <= {'dev'}
    assert goldset.by_segment(result['rows'], 'register') == {
        'darija': {'questions': 1, 'hits': 1, 'first': 1, 'by_door': 1},
        'msa': {'questions': 5, 'hits': 4, 'first': 3, 'by_door': 0},
        'professional': {'questions': 1, 'hits': 1, 'first': 1, 'by_door': 0}}
    assert goldset.by_segment([{'hit': True, 'first': False, 'by_door': False}], 'set') == {
        '-': {'questions': 1, 'hits': 1, 'first': 0, 'by_door': 0}}
    assert goldset.evaluate(sets / 'test.json')['rows'][0]['split'] == 'test'
    # A famous article's card (famous.py) answers first, above the texts (the words alone lead to a law of fees).
    (sets.parent / 'famous.json').write_text(json.dumps({'questions': [
        {'q': '490', 'expect': '/ma/dahir/1-59-413/art_490'}]}))
    row = goldset.evaluate(sets.parent / 'famous.json')['rows'][0]
    assert (row['hit'], row['first'], row['top'][0], row['shown'][0]) == (True, True, '/ma/dahir/1-59-413/art_490',
                                                                          '/ma/dahir/1-59-413/art_490')
    assert row['top'][1] == '/ma/loi/95-97'


def law(akn: str, title: str, label: str, body: str):
    text = Text.objects.create(akn_uri=akn, type='law', number=akn.rsplit('/', 1)[1], title_ar=title)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2015, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    number = label.split()[-1]
    Article.objects.create(version=v, order=1, label=label, number=number, eid=f'art_{number}', body=body)


def test_the_top_three_and_the_first_two_doors_are_what_counts(sets, tmp_path):
    """A question is answered by its first two doors, never a third; by the search's first three texts, never a
    fourth; «by a door» only when the search did not answer it too."""
    law('/akn/ma/act/loi/52-05', 'القانون رقم 52.05 المتعلق بمدونة السير على الطرق', 'المادة 197', 'يسجل الرادار السرعة.')
    for n, words in enumerate(('', ' كلمة', ' كلمة كلمة', ' كلمة كلمة كلمة'), 1):      # the shortest ranks first
        law(f'/akn/ma/act/loi/9{n}-11', f'قانون رقم 9{n}.11', 'المادة 1', f'زمرد{words}.')
    rebuild(log=lambda m: None)
    many = 'شدني الرادار الطلاق النفقة'          # three doors: the radar's, the family's ways, the family's money
    questions = [
        {'q': many, 'expect': '/ma/loi/70-03/art_100'},          # cited by the second door alone
        {'q': many, 'expect': '/ma/dahir/1-59-413/art_479'},     # by the third alone
        {'q': 'شدني الرادار', 'expect': '/ma/loi/52-05/art_197'},  # found by the search, and cited by the door
        {'q': 'المادة 2 من القانون رقم 91.97', 'expect': '/ma/loi/91-97/art_2'},
        {'q': 'مدونة الأسرة', 'expect': 'missing:labour'},        # a code not held here, not that one
        {'q': 'القانون الجنائي', 'expect': 'missing:penal'},      # that code, and on the site
        *({'q': 'زمرد', 'expect': f'/ma/loi/9{n}-11/art_1'} for n in range(1, 5))]
    (tmp_path / 'more.json').write_text(json.dumps({'questions': questions}, ensure_ascii=False))
    result = goldset.evaluate(tmp_path / 'more.json')
    assert [(r['hit'], r['first'], r['by_door']) for r in result['rows']] == [
        (True, True, True), (False, False, False), (True, True, False), (True, True, False), (False, False, False),
        (False, False, False), (True, True, False), (True, False, False), (True, False, False), (False, False, False)]
    assert (result['questions'], result['hits'], result['rate'], result['first'], result['by_door']) == (10, 6, 0.6, 4, 1)
    assert result['rows'][3]['top'][:2] == ['/ma/loi/91-97/art_2', '/ma/loi/91-97']          # the cited article, then its text
    # A set with no question: nothing counted, no rate.
    (tmp_path / 'none.json').write_text(json.dumps({'questions': []}))
    assert goldset.evaluate(tmp_path / 'none.json') == {'questions': 0, 'hits': 0, 'rate': 0.0, 'first': 0, 'by_door': 0,
                                                        'rows': []}


def test_search_eval_says_each_question_and_keeps_the_totals(sets, settings):
    said = run('search_eval', '--set', str(sets / 'mine.json'), '--by', 'register, intent')
    lines = said.splitlines()
    assert lines[:7] == [
        "ok 1 الإفراغ  →  /ma/loi/91-97/art_2  (words, msa, words)",
        "ok 1 القانون رقم 91.97  →  ['/ma/loi/91-97']  (citation, professional, citation)",
        "ok 1 مدونة الأسرة  →  missing:family  (citation, msa, name)",
        "ok d شدني الرادار  →  /ma/loi/52-05/art_141  (words, darija, words)",
        "ok 1 ج.ر 7533  →  /bo/general_ar/7533  (citation, msa, citation)",
        "MISS تأشيرة الدخول  →  /ma/loi/91-97/art_1  (words, msa, question)  not in the law",
        "ok   إفراغ  →  /ma/loi/91-97/art_3  (words, msa, words)"]
    assert '\n6 of 7 in the top 3: 86%; 5 first; 1 of them by a door the question names' in said
    assert '\nby register:\n  darija            1 of    1 (100%), 1 first, 1 by a door\n' in said
    assert '\nby intent:\n  citation          2 of    2 (100%), 2 first, 0 by a door\n' in said
    assert 'graded' not in said
    kept = json.loads(next((settings.CORPUS_DIR / 'reports').glob('search_eval_mine_*.json')).read_text())
    assert (kept['questions'], kept['hits'], kept['first'], kept['by_door'], kept['graded']) == (7, 6, 5, 1, None)
    assert kept['segments']['set'] == {'mine': {'questions': 7, 'hits': 6, 'first': 5, 'by_door': 1}}
    assert [r['q'] for r in kept['rows']] == [q['q'] for q in MINE]
    # A set by its name; under the bar, it fails; a set that is not here is named among those that are.
    with pytest.raises(CommandError, match='86% is under the bar of 90%'):
        run('search_eval', '--set', 'mine', '--min', '0.9')
    assert '\n6 of 7 in the top 3' in run('search_eval', '--set', 'mine', '--min', repr(6 / 7))     # at the bar: passes
    with pytest.raises(CommandError, match=r'No set named road here: the sets are mine, other\.'):
        run('search_eval', '--set', 'road')


def test_the_test_set_shows_its_totals_only_and_every_set_runs_by_split(sets, settings):
    said = run('search_eval', '--test')
    assert said.strip() == '1 of 1 in the top 3: 100%; 1 first; 0 of them by a door the question names'
    kept = json.loads(next((settings.CORPUS_DIR / 'reports').glob('search_eval_test_*.json')).read_text())
    assert 'rows' not in kept and kept['segments']['split'] == {'test': {'questions': 1, 'hits': 1, 'first': 1, 'by_door': 0}}
    said = run('search_eval', '--all', '--split', 'tune', '--by', 'set')
    kept = json.loads(next((settings.CORPUS_DIR / 'reports').glob('search_eval_all_tune_*.json')).read_text())
    assert {r['set'] for r in kept['rows']} <= {'mine', 'other'} and all(r['split'] == 'tune' for r in kept['rows'])
    assert kept['questions'] == sum(goldset.split_of(q['q']) == 'tune' for q in [*MINE, {'q': 'الكراء'}, {'q': 'المكتري'}])
    (sets / 'test.json').unlink()
    with pytest.raises(CommandError, match='No test set yet'):
        run('search_eval', '--test')


def grading(cid, params):
    """The judge: 3 for an article that holds «الإفراغ», 0 for the rest, by the numbers it was sent."""
    blocks = params['messages'][0]['content'].split('\n\n')[1:]
    return {'grades': [{'n': n, 'grade': 3 if 'الإفراغ' in b.split('\n', 1)[1] else 0, 'why': 'x'}
                       for n, b in enumerate(blocks, 1)]}


def test_the_judge_grades_what_search_showed_and_the_measures_follow(sets, settings, monkeypatch, tmp_path):
    sent = claude.install(monkeypatch, settings, tmp_path, grading)
    said = run('grade_answers', '--tuning', '--negatives', '1')
    # Without --write, nothing is sent, and no unrelated articles are drawn.
    assert sent.requests() == [] and said.startswith('9 questions, ') and not (tmp_path / judge.NEGATIVES).exists()
    said = run('grade_answers', '--tuning', '--test', '--negatives', '1', '--write')
    pairs = sum(len(r['params']['messages'][0]['content'].split('\n\n')) - 1 for r in sent.requests())
    assert said.startswith(f'10 questions, {pairs} pairs to grade in {len(sent.requests())} requests;')
    assert f'\n{pairs} of {pairs} pairs graded\n' in said
    grades = {(r['q'], r['path']): r['grade'] for r in map(json.loads, (tmp_path / judge.FILE).read_text().splitlines())}
    assert grades[('الإفراغ', '/ma/loi/91-97/art_2')] == 3 and grades[('الكراء', '/ma/loi/91-97/art_1')] == 0
    # The unrelated articles slipped in for one question, from another set's answers.
    planted = json.loads((tmp_path / judge.NEGATIVES).read_text())
    assert len(planted) == 1 and all(len(p) == 2 for p in planted.values())
    # Eight questions have a grade (not a code not held here, nor a door's article the site lacks, nor an issue's card).
    assert "\ngraded measures: {'questions': 8, 'ndcg10': 0.408, 'mrr': 0.375, 'recall20': 0.5}\n" in said
    assert ("\njudge checks (provisional, until lawyers calibrate it): {'expected_graded': 6, 'expected_2_or_3': 2, "
            "'expected_share': 0.333, 'unrelated_graded': 2, 'unrelated_0': 2, 'unrelated_0_or_1': 2}\n") in said
    # Graded once: nothing to send again.
    again = run('grade_answers', '--tuning', '--test', '--write')
    assert again.startswith('10 questions, 0 pairs to grade in 0 requests; worst case $0')
    # search_eval reads the grades it finds.
    said = run('search_eval', '--set', 'mine', '--by', 'register')
    assert said.endswith('\ngraded (5 questions): nDCG@10 0.526, MRR 0.5, recall@20 0.6\n'
                         '  register msa            nDCG@10 0.5, MRR 0.5, recall@20 0.5 (4)\n'
                         '  register professional   nDCG@10 0.631, MRR 0.5, recall@20 1.0 (1)\n')
    assert 'register darija' not in said                  # the door's article is not held here: nothing graded
    # Grades kept, none for these questions: no graded line.
    (tmp_path / 'ungraded.json').write_text(json.dumps({'questions': [{'q': 'مدونة الأسرة', 'expect': 'missing:family'}]},
                                                       ensure_ascii=False))
    assert 'graded' not in run('search_eval', '--set', str(tmp_path / 'ungraded.json'))
