"""Each constitution's articles traced to the one before (C5 of the constitution review): from the meaning vectors
search holds and the articles' words, `same`, `changed`, `none` (nothing near) or `unsure` (kept for a person and never
shown); `trace_constitutions` writes the lineage the constitution's pages read."""
import json
from io import StringIO

import numpy as np
import pytest
from django.core.management import call_command

from apps.corpus.models import Article
from apps.corpus.services import constitutions
from apps.corpus.services.addresses import text_path
from apps.corpus.tests.test_constitutions import URIS, make
from apps.search.models import SearchPassage

pytestmark = pytest.mark.django_db
YEARS = {1962: '—', 1970: '1.70.177', 1972: '1.72.061', 1992: '1.92.155', 1996: '1.96.157', 2011: '1.11.91'}
SAME = 'السيادة للأمة تمارسها مباشرة بالاستفتاء وبصفة غير مباشرة بواسطة المؤسسات الدستورية'


def axis(*weights):
    """A unit vector of the meaning model's 1024 dimensions, its first ones given."""
    v = np.zeros(1024, dtype=np.float32)
    v[:len(weights)] = weights
    return (v / np.linalg.norm(v)).tolist()


ARTICLES = {
    'art_2': (SAME, axis(1)),                                     # the same words, the same meaning, every year
    'art_5': (None, axis(0, 1)),                                  # the same meaning, its words changed every year
}
# The thresholds the cases below stand on, each clearly on one side: meaning ≥ LIKE is the same article; each the
# other's nearest at MUTUAL or more is too; under UNLIKE with almost no word shared is nothing near.
LIKE, MUTUAL, UNLIKE = 0.80, 0.70, 0.66
NEW_IN_1996 = {
    'art_40': ('تضمن الدولة حرية التنقل والاستقرار لجميع المواطنين', axis(0, 0, 0, 0, 0, 1)),
    'art_43': ('يحدد النص شروط تنظيم المهن الحرة وممارستها داخل التراب الوطني', axis(0, 0, 0, 0, 0, 0, 0, 1)),
    'art_44': ('تسهر المحكمة العليا على احترام الأحكام وتبت في المنازعات', axis(*[0] * 9, 1)),
}
NEW_IN_2011 = {
    # Nothing near (meaning 0, no word shared).
    'art_31': ('تعمل الدولة على تعبئة كل الوسائل المتاحة لتيسير أسباب استفادة المواطنين من العلاج', axis(0, 0, 1)),
    # Meaning 0.75 to art_2, under LIKE; art_2's nearest is itself, so not each other's: unsure.
    'art_32': ('الأسرة القائمة على علاقة الزواج الشرعي هي الخلية الأساسية للمجتمع', axis(0.75, 0, 0, 0.66)),
    # Meaning 0.75 to art_40, under LIKE, other words: changed only because each is the other's nearest.
    'art_41': ('يمارس البرلمان السلطة التشريعية ويصوت على القوانين', axis(0, 0, 0, 0, 0, 0.75, 0.66)),
    # Meaning 0.4 to art_43, under UNLIKE: changed only by its words, seven of ten alike (0.7).
    'art_42': ('يحدد المرسوم شروط تنظيم الحرف الحرة وممارستها داخل التراب المغربي',
               axis(0, 0, 0, 0, 0, 0, 0, 0.4, 0.9165)),
    # Meaning 1 to art_44 (other words): changed, and art_44's nearest.
    'art_46': ('تحدث محكمة عليا للنظر في الطعون الانتخابية', axis(*[0] * 9, 1)),
    # Meaning 0.85 to art_44, over LIKE, though art_44's nearest is art_46: changed by its meaning alone.
    'art_45': ('يعين الملك رئيس الحكومة من الحزب المتصدر للانتخابات', axis(*[0] * 9, 0.85, 0.5268)),
    # Meaning 0.5 to art_44, under UNLIKE, words little alike (0.24) but two of its eight shared: unsure, not none.
    'art_47': ('تسهر الهيئة الوطنية على ضبط قواعد المنافسة والأسعار', axis(*[0] * 9, 0.5, 0, 0.866)),
}


@pytest.fixture
def lineage_file(tmp_path, monkeypatch):
    monkeypatch.setattr(constitutions, 'LINEAGE', tmp_path / 'constitution_lineage.json')
    constitutions._lineage.cache_clear()
    yield tmp_path / 'constitution_lineage.json'
    constitutions._lineage.cache_clear()


def held():
    for year, number in YEARS.items():
        version = make(year, number, 'in_force' if year == 2011 else 'repealed').versions.get()
        rows = {**ARTICLES, **{1996: NEW_IN_1996, 2011: NEW_IN_2011}.get(year, {})}
        for order, (eid, (body, vector)) in enumerate(rows.items(), 1):
            body = body or f'يصدر الملك الأمر بتنفيذ القانون خلال أجل {year} يوما'
            Article.objects.create(version=version, order=order, eid=eid, label=f'الفصل {eid[4:]}', number=eid[4:],
                                   body=body)
            SearchPassage.objects.create(path=f'{text_path(URIS[year])}/{eid}', text_path=text_path(URIS[year]),
                                         model='bge-m3', vector=vector)


def test_each_article_is_traced_by_meaning_and_words_and_the_lineage_is_written(lineage_file):
    held()
    out = StringIO()
    call_command('trace_constitutions', stdout=out)
    data = json.loads(lineage_file.read_text())
    assert data['model'] == 'bge-m3' and data['checked'] == '' and list(data['pairs']) == ['1970', '1972', '1992',
                                                                                           '1996', '2011']
    links = data['pairs']['2011']['links']
    assert data['pairs']['2011']['from'] == 1996
    assert links['art_2'][:2] == ['art_2', 'same'] and links['art_5'][:3] == ['art_5', 'changed', 1.0]
    assert links['art_31'][:2] == ['', 'none']
    assert links['art_32'][:2] == ['art_2', 'unsure'] and links['art_32'][2] == pytest.approx(0.751, abs=0.001)
    assert (constitutions.LIKE, constitutions.MUTUAL, constitutions.UNLIKE) == (LIKE, MUTUAL, UNLIKE)
    mutual = links['art_41']
    assert mutual[:2] == ['art_40', 'changed'] and MUTUAL < mutual[2] < LIKE and mutual[3] < 0.5
    assert mutual[2] == pytest.approx(0.751, abs=0.001) and mutual[3] == 0.0
    worded = links['art_42']
    assert worded[:2] == ['art_43', 'changed'] and worded[2] < UNLIKE and 0.5 < worded[3] < 0.9
    assert worded[2] == pytest.approx(0.4, abs=0.001) and worded[3] == 0.7
    assert links['art_46'][:3] == ['art_44', 'changed', 1.0]
    alone = links['art_45']
    assert alone[:2] == ['art_44', 'changed'] and alone[2] > LIKE and alone[2] == pytest.approx(0.85, abs=0.001)
    assert alone[3] < 0.5
    shared = links['art_47']
    assert shared[:2] == ['art_44', 'unsure'] and shared[2] < UNLIKE and shared[3] == pytest.approx(0.235, abs=0.001)
    # 1996's new articles stand near nothing of 1992's.
    assert {e: data['pairs']['1996']['links'][e][:2] for e in NEW_IN_1996} == {e: ['', 'none'] for e in NEW_IN_1996}
    assert out.getvalue().splitlines() == ['1962 → 1970: changed 1, same 1', '1970 → 1972: changed 1, same 1',
                                           '1972 → 1992: changed 1, same 1', '1992 → 1996: changed 1, none 3, same 1',
                                           '1996 → 2011: changed 5, none 1, same 1, unsure 2']
    # The constitution's page follows an article back through every year, with the words each one changed.
    rows = constitutions.lineage('/ma/dahir/1-11-91/art_5')['rows']
    assert [(r['year'], r['state']) for r in rows] == [(1962, ''), (1970, 'changed'), (1972, 'changed'),
                                                       (1992, 'changed'), (1996, 'changed'), (2011, 'changed')]
    assert rows[-1]['diff'] == [['=', 'يصدر الملك الأمر بتنفيذ القانون خلال أجل'], ['-', '1996'], ['+', '2011'],
                                ['=', 'يوما']]
    # Followed forward from 1962, the same article stands in every one.
    assert [r['path'] for r in constitutions.lineage('/ma/dahir/constitution-1962/art_2')['rows']][-1] == \
        '/ma/dahir/1-11-91/art_2'


def test_words_that_changed_only_their_spelling_are_not_a_change():
    assert constitutions.changed_words('ماعدا اذا قرر الملك ذلك', 'ما عدا إذا قرر الملك ذلك') == [
        ['=', 'ما عدا إذا قرر الملك ذلك']]


def test_a_constitution_is_named_as_people_cite_it():
    t = make(1996, '1.96.157')
    assert constitutions.cited_as(t) == 'دستور 1996'
    assert constitutions.cited_as(type(t)(akn_uri='/akn/ma/act/loi/52-05')) is None
