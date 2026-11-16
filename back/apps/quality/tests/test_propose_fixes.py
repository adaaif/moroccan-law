"""A1 of the consumer plan: corrections two other copies agree on. The SGG's copy set word by word beside Adala's, each
place they part judged by the BO's reading of the page; what the judge settles goes to a file apply_page_reading takes,
the rest is listed for a person."""
from datetime import date
from pathlib import Path

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Document

pytestmark = pytest.mark.django_db

URI = '/akn/ma/act/loi/31-08'
# (number, the SGG's words, Adala's, the BO's), in the SGG's order.
ARTICLES = [
    # «القرض» stands elsewhere in the BO's article: the place is judged with a word each side.
    ('10', 'يطالب القرض به ويؤدي القرض في أجل', 'يطالب المقرض به ويؤدي القرض في أجل', 'يطالب المقرض به ويؤدي القرض في أجل'),
    # The SGG's layer cut a word in two; the BO's reading holds both forms, and the letters agree.
    ('9', 'تحدد البيانات والم خالصات المسلمة', 'تحدد البيانات والمخالصات المسلمة',
     'تحدد البيانات والم خالصات المسلمة وتسلم والمخالصات'),
    # The BO reads as the SGG does: a place for a person.
    ('3', 'يعاقب بغرامة من ألف درهم', 'يعاقب بغرامة من ألفي درهم', 'يعاقب بغرامة من ألف درهم'),
    ('4', 'ينشر هذا القانون .', 'ينشر هذا القانون', 'ينشر هذا القانون'),            # a stop alone parts them
    # The SGG's words stand twice in its article: not found once, so not written as a fix.
    ('5', 'في أجل ثلاثة أشهر في أجل ثلاثة أشهر', 'في أجل ثلاث أشهر في أجل ثلاثة أشهر', 'في أجل ثلاث أشهر'),
    ('6', 'تحدد النسبة بنص', 'تحدد النسب بنص', 'تحدد النسب بنص'),                    # changed since the BO: --changed
    ('7', 'مادة لا يحملها عدالة', None, 'مادة لا يحملها عدالة'),
    ('8', 'مادة لم تقرأ', 'مادة لم تقرا بعد', None),                               # the BO's page holds no article 8
    # The SGG's layer glued two words; the BO's reading glued them too, its letters are Adala's.
    ('11', 'يؤدون عملهمن بأمانة', 'يؤدون عملهم من بأمانة', 'يؤدون عملهممن بأمانة'),
    # The BO's page reads both, each between the same words: it settles nothing.
    ('12', 'يطالب القرض به', 'يطالب المقرض به', 'يطالب المقرض به ثم يطالب القرض به'),
]


def version(text, consolidation, day, column, document=None):
    v = Version.objects.create(text=text, language='ar', valid_from=day, consolidation=consolidation,
                               source_document=document)
    for k, row in enumerate(ARTICLES, 1):
        if row[column] is not None:
            Article.objects.create(version=v, order=k, label=f'المادة {row[0]}', number=row[0], eid=f'art_{row[0]}',
                                   body=row[column])
    return v


@pytest.fixture
def consumer():
    text = Text.objects.create(akn_uri=URI, type='law', number='31-08', title_ar='القانون رقم 31.08')
    sgg = Document.objects.create(source='sgg', kind='consolidated_text', sha256='c' * 64, path='sources/sgg/31-08.pdf',
                                  mime='application/pdf', bytes=1, language='ar', fetched_at=timezone.now())
    version(text, Consolidation.SGG, date(2019, 1, 1), 1, sgg)
    version(text, Consolidation.ADALA, date(2020, 1, 1), 2)
    Version.objects.create(text=text, language='ar', valid_from=date(2015, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    version(text, Consolidation.AS_PUBLISHED, date(2011, 4, 7), 3)        # the first printing judges
    return text


def test_the_places_both_other_copies_agree_on_are_written_for_apply_page_reading(consumer, tmp_path, capsys):
    out = tmp_path / 'consumer_31_08.yaml'
    before = date.today()
    call_command('propose_fixes', URI, '--out', str(out), '--changed', '6, ', '--show', '2')
    after = date.today()
    written = out.read_text(encoding='utf-8')
    assert 'wrong: يطالب القرض به' in written                         # the words as they read, not escaped
    assert written.startswith('# /ma/loi/31-08 as the SGG prints it, put right where adala\'s copy and the as_published '
                              'reading of the BO page agree (propose_fixes, A1 of the consumer plan).\n')
    data = yaml.safe_load(written)
    assert list(data) == ['text', 'document', 'read_on', 'fixes', 'notes', 'checked']
    assert data.pop('read_on') in {str(before), str(after)}
    assert data == {'text': '/ma/loi/31-08', 'document': 'sources/sgg/31-08.pdf', 'fixes': [
        {'arts': ['10'], 'wrong': 'يطالب القرض به', 'right': 'يطالب المقرض به'},
        {'arts': ['9'], 'wrong': 'البيانات والم خالصات المسلمة', 'right': 'البيانات والمخالصات المسلمة'},
        {'arts': ['11'], 'wrong': 'يؤدون عملهمن بأمانة', 'right': 'يؤدون عملهم من بأمانة'}],
        'notes': [], 'checked': ['9', '10', '11']}
    assert capsys.readouterr().out.splitlines() == [
        f'{URI}: 3 corrections written to {out}; 4 places left for a person',
        '   ? 3: «من ألف درهم» / adala: «من ألفي درهم»',
        '   ? 5: «أجل ثلاثة أشهر» / adala: «أجل ثلاث أشهر»']
    # The file is one apply_page_reading takes: the SGG's article put right.
    call_command('apply_page_reading', str(out))
    sgg = Article.objects.filter(version__consolidation=Consolidation.SGG)
    assert sgg.get(number='10').body == 'يطالب المقرض به ويؤدي القرض في أجل'
    assert sgg.get(number='9').body == 'تحدد البيانات والمخالصات المسلمة'
    assert sgg.get(number='11').body == 'يؤدون عملهم من بأمانة'


def test_an_article_changed_since_the_bo_is_judged_when_not_named(consumer, tmp_path, capsys):
    Version.objects.filter(consolidation=Consolidation.SGG).update(source_document=None)
    call_command('propose_fixes', URI, '--out', str(tmp_path / 'fixes.yaml'), '--show', '0')
    data = yaml.safe_load((tmp_path / 'fixes.yaml').read_text(encoding='utf-8'))
    assert [f['arts'] for f in data['fixes']] == [['10'], ['9'], ['6'], ['11']] and data['document'] == ''
    assert capsys.readouterr().out.splitlines() == [
        f'{URI}: 4 corrections written to {tmp_path / "fixes.yaml"}; 4 places left for a person']


def test_a_text_needs_its_three_copies(consumer, tmp_path):
    with pytest.raises(CommandError, match='/akn/ma/act/loi/9-99: not in the corpus'):
        call_command('propose_fixes', '/akn/ma/act/loi/9-99', '--out', str(tmp_path / 'x.yaml'))
    with pytest.raises(CommandError, match=f'{URI}: needs its dgi, adala and as_published versions'):
        call_command('propose_fixes', URI, '--base', 'dgi', '--out', str(tmp_path / 'x.yaml'))
    assert not Path(tmp_path / 'x.yaml').exists()
