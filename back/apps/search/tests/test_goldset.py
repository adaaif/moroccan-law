"""B1 and B2 of the search plan: the tuning questions split once and for all, every question's register and intent read
from its words, and the judge's grades turned into nDCG@10, MRR and recall@20."""
import json

from apps.search.services import judge
from apps.search.services.goldset import intent_of, register_of, sets, split_of


def test_a_question_keeps_its_split_and_one_in_four_is_dev():
    questions = [q['q'] for p in sets() for q in json.loads(p.read_text())['questions']]
    assert all(split_of(q) == split_of(q) for q in questions)
    dev = sum(split_of(q) == 'dev' for q in questions) / len(questions)
    assert 0.18 < dev < 0.32


def test_the_register_comes_from_the_label_or_the_words():
    assert register_of({'q': 'x', 'lang': 'arabizi'}) == 'darija_latin'
    assert register_of({'q': 'x', 'lang': 'fr'}) == 'french'
    assert register_of({'q': 'واش نقدر نرجع السلعة'}) == 'darija'
    assert register_of({'q': 'ما هي مدة الإشعار بالإفراغ'}) == 'msa'
    assert register_of({'q': 'wach mol dar y9der ykhrjni'}) == 'darija_latin'
    assert register_of({'q': 'délai de préavis du bail'}) == 'french'
    assert register_of({'q': 'what is the notice period for a tenant in Morocco'}) == 'english'


def test_the_intent_comes_from_the_words():
    assert intent_of('الفصل 418 من ق.ل.ع') == 'citation'
    assert intent_of('مدونة السير') == 'name'
    assert intent_of('شحال التعويض عن الفصل') == 'number'
    assert intent_of('ما معنى النفقة') == 'definition'
    assert intent_of('كيفاش نطلب الطلاق') == 'procedure'
    assert intent_of('واش مول الدار يقدر يخرجني') == 'question'
    assert intent_of('عقد الكراء التجاري') == 'words'


def test_grades_become_ndcg_mrr_and_recall():
    known = {judge.key('q1', '/a/art_1', 'v'): {'grade': 3}, judge.key('q1', '/a/art_2', 'v'): {'grade': 0},
             judge.key('q1', '/a/art_3', 'v'): {'grade': 2}}
    perfect = judge.measure([{'q': 'q1', 'shown': ['/a/art_1', '/a/art_3', '/a/art_2']}], known)
    assert perfect == {'questions': 1, 'ndcg10': 1.0, 'mrr': 1.0, 'recall20': 1.0}
    late = judge.measure([{'q': 'q1', 'shown': ['/a/art_2', '/a/art_1']}], known)
    assert late['mrr'] == 0.5 and late['recall20'] == 0.5 and late['ndcg10'] < 1
    # A question nobody graded is left out rather than counted as a miss.
    assert judge.measure([{'q': 'other', 'shown': ['/a/art_1']}], known)['questions'] == 0


def test_a_batch_answer_becomes_grades_and_a_bad_number_is_dropped():
    meta = {'g1': ('q1', [('/a/art_1', 'v1'), ('/a/art_2', 'v1')])}
    results = {'g1': {'data': {'grades': [{'n': 1, 'grade': 3, 'why': 'answers'}, {'n': 9, 'grade': 2, 'why': 'x'},
                                          {'n': 2, 'grade': 5, 'why': 'x'}]}}}
    rows = judge.collect(results, meta)
    assert [(r['path'], r['grade']) for r in rows] == [('/a/art_1', 3)]
