"""The DGI's edition of the tax code (the tax review, T1): its headings in visual order, its amounts, its notes."""
import pytest

from apps.consolidation.services import dgi
from apps.consolidation.services.instructions import amending


@pytest.mark.parametrize('raw, want', [
    ('المادة -.2 الأشخاص الخاضعون للضريبة', 'المادة 2.- الأشخاص الخاضعون للضريبة'),
    ('المادة .13 - عوائد الأسهم', 'المادة 13.- عوائد الأسهم'),
    ('المادة 20 -. الإقرار', 'المادة 20.- الإقرار'),
    ('المادة -.91الإعفاءات', 'المادة 91.- الإعفاءات'),
    ('المادة 82.- المكررة -إقرار برقم أعمال المقاول الذاتي', 'المادة 82 المكررة.- إقرار برقم أعمال المقاول الذاتي'),
    ('-. عائدات شهادات الصكوك  المادة 14 المكررة⟦2⟧', 'المادة 14 المكررة.- عائدات شهادات الصكوك⟦2⟧'),
    ('. – الجزاءات المتعلقة بالأداء الإلكتروني  المادة 208 المكررة⟦4⟧',
     'المادة 208 المكررة.- الجزاءات المتعلقة بالأداء الإلكتروني⟦4⟧'),
])
def test_a_heading_printed_in_visual_order_is_put_back(raw, want):
    assert dgi.heading(raw) == want


def test_a_sentence_ending_on_an_article_reference_is_not_a_heading():
    line = '- هوية المستفيدين أو رقم تسجيل الإقرار المشار إليه في المادة 4 المكررة مرتين'
    assert dgi.heading(line) == line


@pytest.mark.parametrize('raw, want', [
    ('شريحة الدخل إلى غاية 000 40 درهم', 'شريحة الدخل إلى غاية 40 000 درهم'),
    ('بالنسبة لشريحة %10 الدخل', 'بالنسبة لشريحة 10% الدخل'),
    ('-1° العمليات', '1°- العمليات'),
    ('-.III يتكون إجمالي الدخل', 'III.- يتكون إجمالي الدخل'),
    ('المادة 98.- )تنسخ(', 'المادة 98.- (تنسخ)'),
])
def test_tidy_puts_the_layers_shapes_back(raw, want):
    assert dgi.tidy(raw) == want


def _cut(lines):
    return {a.number: a for a in dgi.cut([lines]).articles}


def test_the_cut_keeps_headings_alone_on_their_line_and_repeals(monkeypatch):
    monkeypatch.setattr('apps.consolidation.services.layer.lexicon', dict)
    arts = _cut([
        'المادة -.1 تعريف',
        'تطبق هذه المدونة.',
        'المادة 2',
        'الأشخاص الخاضعون',
        'يخضع للضريبة كل شخص.',
        'غير المقيمين  المادة -.3 المبالغ الإجمالية',
        'يراد بالمبالغ ما يلي.',
        'المادة -.4 )تنسخ(⟦1⟧',
        'الباب الثاني',
        'المادة -.5 السعر',
        'يحدد السعر في 10%.',
        'كما هو منصوص عليه في المادة 4 أعلاه.',
    ])
    assert list(arts) == ['1', '2', '3', '4', '5']
    assert arts['2'].heading_path[-1] == 'الأشخاص الخاضعون'
    assert arts['4'].lines == ['(تنسخ)⟦1⟧']
    assert arts['5'].heading_path == ['الباب الثاني', 'السعر']


def test_a_footnote_set_at_the_texts_size_leaves_the_body():
    line = 'يخصم ما قدره 600 درهم. تم إدراج هذه الفقرة بمقتضى البند I من المادة 7 من قانون المالية لسنة 2026'
    assert dgi._NOTE_AR.sub('', line).strip() == 'يخصم ما قدره 600 درهم.'
    kept = 'المشار إليه في المادة 4 من قانون المالية رقم 110.13 للسنة المالية 2014'
    assert dgi._NOTE_AR.sub('', kept) == kept


def test_a_finance_law_changes_the_code_it_names_not_the_law_that_made_it():
    lead = ('ابتداء من فاتح يناير 2026، تغير وتتمم أحكام المواد 4 و73-II من المدونة العامة للضرائب المحدثة بموجب المادة 5 '
            'من قانون المالية رقم 43.06 للسنة المالية 2007')
    assert amending._target(lead) == {'code': 'tax'}
    assert amending._target('تغير أحكام المادة 7 من قانون المالية رقم 50.22 للسنة المالية 2023') == {
        'kind': 'law', 'number': '50-22'}


def test_the_french_divisions_before_the_next_article_are_not_its_words():
    body = 'Le taux est fixé à 20%. TITRE II L’IMPOT SUR LE REVENU CHAPITRE PREMIER CHAMP D’APPLICATION'
    assert dgi._FR_DIVISION.split(body, maxsplit=1)[0] == 'Le taux est fixé à 20%.'
    assert dgi._FR_DIVISION.split('visés au Chapitre II ci-dessus.', maxsplit=1)[0] == 'visés au Chapitre II ci-dessus.'


def test_a_wrapped_line_that_starts_on_the_clerks_is_not_a_book(monkeypatch):
    """«يبلغ الكُتّاب مقررو هذه اللجان …»: a line of the 2026 edition's art. 225 that a wrap starts on «الكتاب» headed arts 226–248 as a book
    and cost them their own headings (W11 of the library-search review). A division's second word counts it."""
    monkeypatch.setattr('apps.consolidation.services.layer.lexicon', dict)
    arts = _cut([
        'الكتاب الثاني: المساطر الجبائية',
        'الباب الثاني',
        'المادة -.1 اللجان المحلية لتقدير الضريبة',
        'تحدث الإدارة لجانا محلية. يبلغ',
        'الكتاب مقررو هذه اللجان إلى الطرفين وفق الإجراءات المنصوص عليها في المادة 219 أعلاه خلال',
        'الأربعة أشهر الموالية.',
        'المادة -.2 اللجنة الوطنية للنظر في الطعون المتعلقة بالضريبة',
        'تحدث لجنة دائمة.',
        'الكتاب الثالث',
        'المادة -.3 أحكام مختلفة',
        'تطبق أحكام هذا الكتاب.',
    ])
    assert arts['2'].heading_path == ['الكتاب الثاني: المساطر الجبائية', 'الباب الثاني', 'اللجنة الوطنية للنظر في الطعون المتعلقة بالضريبة']
    assert 'الكتاب مقررو هذه اللجان' in ' '.join(arts['1'].lines)
    assert arts['3'].heading_path[0] == 'الكتاب الثالث'
