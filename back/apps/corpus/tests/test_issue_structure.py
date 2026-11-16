from datetime import date

import pytest
from django.utils import timezone

from apps.corpus.services.issue_structure import split_articles
from apps.sources.models import Document, Edition, Issue, Page


def _lines(*pages):
    return [(page, line) for page, text in pages for line in text.strip().splitlines()]


def test_articles_are_cut_at_their_headings_with_their_divisions_and_pages():
    cut = split_articles(_lines(
        (10, 'ظهير شريف رقم 1.26.58\nقانون رقم 051.26\nالباب الأول\nمقتضيات عامة\nالمادة الأولى\nالعدل مساعد للقضاء.'),
        (11, 'المادة 2\nيتقيد العدل.\nالباب الثاني\nالولوج إلى المهنة\nالمــادة 3. - يشترط في المترشح :\n- أن يكون مغربيا ؛'),
    ))
    assert cut['front'] == 'ظهير شريف رقم 1.26.58\nقانون رقم 051.26'
    assert [(a['label'], a['page']) for a in cut['articles']] == [
        ('المادة الأولى', 10), ('المادة 2', 11), ('المادة 3', 11)]
    assert cut['articles'][0]['heading_path'] == ['الباب الأول: مقتضيات عامة']
    assert cut['articles'][2]['heading_path'] == ['الباب الثاني: الولوج إلى المهنة']
    assert cut['articles'][2]['body'] == 'يشترط في المترشح :\n- أن يكون مغربيا ؛'


def test_an_amending_laws_quoted_articles_stay_in_the_article_that_quotes_them():
    cut = split_articles(_lines((5, '''
المادة الأولى
تغير وتتمم أحكام المادة 82 من القانون التنظيمي رقم 111.14 :
«المادة 82. - تشتمل الاختصاصات الذاتية للجهة
المادة الخامسة
- الميادين التالية.»
المادة الثانية
ينشر هذا القانون بالجريدة الرسمية.''')))
    assert [a['label'] for a in cut['articles']] == ['المادة الأولى', 'المادة الثانية']
    assert 'المادة الخامسة' in cut['articles'][0]['body']   # its « lost by the OCR, still not a new article


def test_a_lost_heading_is_forgiven_and_a_table_title_is_not_an_article():
    cut = split_articles(_lines((7, '''
المادة 1
أ.
المادة 3
ج.
المادة 4 مكرر
د.
الجدول "أ"
المادة "8"
| الموارد | 10,00 |''')))
    assert [a['label'] for a in cut['articles']] == ['المادة 1', 'المادة 3', 'المادة 4 مكرر']
    assert cut['tail'].startswith('الجدول "أ"')


def test_the_short_line_above_an_article_is_its_subject_not_the_end_of_the_one_before():
    cut = split_articles(_lines((9690, '''
المادة 1
يصادق على المرسوم التالي.
إحداث مناصب مالية
المادة 2
يتم إحداث 36.895 منصبا ماليا.
- لفائدة الوزارات التالية
المادة 3
تلغى اعتمادات الأداء.''')))
    assert [a['heading_path'] for a in cut['articles']] == [[], ['إحداث مناصب مالية'], []]
    assert cut['articles'][0]['body'] == 'يصادق على المرسوم التالي.'
    assert cut['articles'][1]['body'] == 'يتم إحداث 36.895 منصبا ماليا.\n- لفائدة الوزارات التالية'


def test_markdown_heading_marks_do_not_hide_an_article(tmp_path):
    from apps.corpus.services.issue_structure import _MARKS
    assert _MARKS.sub('', '## المادة 38').strip() == 'المادة 38'
    assert _MARKS.sub('', '**المادة 38**').strip() == 'المادة 38'


def test_a_heading_read_left_to_right_is_still_a_heading():
    cut = split_articles(_lines((1, 'المادة 1\nأ.\n2 المادة\nب.\nالمادة 3\nج.')))
    assert [a['label'] for a in cut['articles']] == ['المادة 1', 'المادة 2', 'المادة 3']


def test_headings_the_ocr_lost_are_forgiven_when_the_next_ones_carry_on():
    cut = split_articles(_lines((1, 'المادة 1\nأ.\nالمادة 2\nب.\nالمادة 3\nج.\nالمادة 6\nو.\nالمادة 7\nز.\nالمادة 8\nح.')))
    assert [a['label'] for a in cut['articles']] == ['المادة 1', 'المادة 2', 'المادة 3', 'المادة 6', 'المادة 7', 'المادة 8']


def test_a_text_is_found_by_its_number_on_the_next_line_or_by_a_councils_number():
    from apps.corpus.services.issue_structure import _start_of
    lines = [(7090, 'مقتضيات سابقة.'), (7091, 'قرار لوزير التعليم العالي والبحث العلمي والابتكار'),
             (7091, 'رقم 1524.26 صادر في فاتح صفر 1448'), (7092, 'قرار لمجلس المنافسة عدد 2026/ق/120 صادر في 3 محرم 1448')]
    assert _start_of(lines, {'title': 'قرار لوزير التعليم العالي رقم 1524.26 صادر في', 'page': 7091}, 0) == 1
    assert _start_of(lines, {'title': 'قرار لمجلس المنافسة عدد 2026/ق/120 صادر في', 'page': 7092}, 0) == 3


def test_an_old_dahir_printed_as_its_kind_alone_is_found_by_the_subject_under_it():
    """The Bulletin-from-No.-1 review: before 1956 «ظهير شريف» stands alone, centred, its subject on the next line (BO 1381)."""
    from apps.corpus.services.issue_structure import _start_of
    lines = [(657, 'ظهير شريف في ضبط صناعة واصلاح الالات المعدة لتوليد البخار ........ 657'),
             (657, 'الحمد لله وحده'), (657, 'ظهير شريف'),
             (657, 'في ضبط صناعة واصلاح الالات المعدة لتوليد البخار والاوعية ذات ضغط بخاري'),
             (657, 'يعلم من كتابنا هذا اسماه الله واعز امره اننا اصدرنا امرنا الشريف بما يأتي')]
    entry = {'title': 'ظهير شريف في ضبط صناعة واصلاح الالات المعدة لتوليد البخار والاوعية ذات ضغط بخاري',
             'page': 657, 'number_as_printed': ''}
    assert _start_of(lines, entry, 0) == 2


def test_a_law_of_one_article_and_a_title_that_stops_at_its_statement_of_reasons():
    from apps.corpus.services.issue_structure import as_law, split_articles
    lines = [(5000, 'قانون رقم 63.24 يوافق بموجبه على الاتفاقية رقم 185'), (5000, 'مادة فريدة'),
             (5000, 'يوافق على الاتفاقية رقم 185 بشأن وثائق هوية البحارة.'), (5001, 'وحرر بالرباط في 3 يونيو 2025.')]
    cut = split_articles(lines)
    assert [(a['label'], a['body']) for a in cut['articles']] == [('مادة فريدة', 'يوافق على الاتفاقية رقم 185 بشأن وثائق هوية البحارة.')]
    assert cut['front'] == 'قانون رقم 63.24 يوافق بموجبه على الاتفاقية رقم 185' and cut['tail'].startswith('وحرر')
    data = {'type': 'law', 'title': '', 'number_as_printed': '58.25', 'promulgating_dahir': ''}
    front = 'قانون رقم 58.25\nيتعلق بالمسطرة المدنية\nبيان الأسباب\nإذا كان القانون رقم 38.15 …'
    assert as_law(data, front)['title'] == 'قانون رقم 58.25 يتعلق بالمسطرة المدنية'


@pytest.mark.django_db
def test_a_contents_cut_short_is_read_again_in_two_halves_by_the_page_of_its_entries(monkeypatch):
    from apps.corpus.services import issue_structure
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='7155' * 16, path='BO_7155_ar.pdf',
                                  mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now(),
                                  page_count=90)
    for i in range(8):
        Page.objects.create(document=doc, index=i, printed_number=8313 + i, text=f'فهرست {i}')
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7155, date=date(2022, 12, 26), document=doc)
    entry = lambda page: {'title': f'قرار {page}', 'page': page}
    calls = []

    def batch(kind, requests, log=print):
        calls.append([r['params']['system'][-40:] for r in requests])
        if len(requests) == 1:
            return {'toc-7155': {'data': None, 'stop': 'max_tokens', 'error': 'not JSON'}}
        return {'toc-7155-0': {'data': {'entries': [entry(8314), entry(8357), entry(8380)]}, 'stop': 'end_turn', 'error': ''},
                'toc-7155-1': {'data': {'entries': [entry(8357), entry(8358), entry(8400)]}, 'stop': 'end_turn', 'error': ''}}

    monkeypatch.setattr(issue_structure.toc, 'run_batch', batch)          # where read_toc looks it up
    entries = issue_structure.read_toc(issue, 'claude-haiku-5-5', log=lambda *a: None)
    assert [e['page'] for e in entries] == [8314, 8357, 8358, 8400]
    assert len(calls) == 2 and calls[1][0].endswith('before 8358.') and calls[1][1].endswith('8358 or after.')
    calls.clear()
    issue_structure.read_toc(issue, 'claude-haiku-5-5', log=lambda *a: None, halves=True)
    assert len(calls) == 1 and len(calls[0]) == 2


def test_a_tables_last_row_stays_in_its_article_and_is_never_the_next_ones_subject():
    """T3 of the work plan: decree 2.25.265's last pension row stood over its art. 3 as a subject."""
    from apps.corpus.services.issue_structure import split_articles
    lines = [(2389, 'المادة الأولى'), (2389, 'يحدد المبلغ الشهري.'), (2389, 'المادة الثانية'),
             (2389, 'يحدد المبلغ الأدنى على النحو التالي :'),
             (2389, '| 900 | من 2473 يوما إلى 2856 يوما |'), (2389, '| 1000 | 2857 يوما فما فوق |'),
             (2389, 'المادة الثالثة'), (2389, 'ينسخ المرسوم رقم 2.96.318.')]
    _, second, third = split_articles(lines)['articles']
    assert second['body'].endswith('| 1000 | 2857 يوما فما فوق |') and third['heading_path'] == []


def test_an_old_scans_texts_are_found_elongated_reversed_or_without_a_number():
    """The Bulletin-to-1956 review: the 1956–2018 scans' readings keep the print's elongations, may give a number's
    parts in visual order, and the 1960s orders carry no number; the pilot found 281 of 380 legal texts before."""
    from apps.corpus.services.issue_structure import _start_of
    lines = [(741, 'تتمة النص السابق.'),
             (742, 'قـرار لـوزيـر الــداخليـة رقـم 446.86 صـادر فـي 8 رجـــب 1406'),
             (743, 'قرار لوزير المالية رقم 86.563 صادر في 15 من شعبان 1406 (25 أبريل 1986)'),
             (744, 'قرار لوزير الصحة العمومية بتاريخ 4 مارس 1964 يحدد بموجبه'),
             (744, 'تاريخ المباراة الخاصة بولوج مدرسة الاطارات لتكوين ممرضين')]
    assert _start_of(lines, {'title': 'قرار لوزير الداخلية رقم 446.86 صادر في 8 رجب 1406', 'page': 742}, 0) == 1
    assert _start_of(lines, {'title': 'قرار لوزير المالية رقم 563.86 صادر في 15 من شعبان 1406', 'page': 743}, 0) == 2
    unnumbered = {'title': 'قرار لوزير الصحة العمومية بتاريخ 4 مارس 1964 يحدد بموجبه تاريخ المباراة الخاصة بولوج '
                           'مدرسة الاطارات', 'page': 744}
    assert _start_of(lines, unnumbered, 0) == 3
    assert _start_of(lines, {'title': 'وزارة العدل – محكمة السدد بالقنيطرة – بيع عقار', 'page': 744}, 0) is None


def test_numbers_printed_with_other_separators_a_number_given_apart_and_a_royal_charter_are_found():
    """31 Oct 2026: BO 2984 lists «588-67» and prints «588.67»; BO 3565 lists «667.64» and prints «64. 667»; BO 3240
    lists a convention by its title with its dahir's number apart; BO 2378's Royal Charter has neither number nor kind."""
    from apps.corpus.services.issue_structure import _start_of
    lines = [(3, 'نصوص عامة'), (3, 'ظهير شريف رقم 588.67 بتاريخ 8 شعبان 1389 بالمصادقة على أعمال مؤتمر'),
             (187, 'الشروط النموذجية العامة لعقود التأمين من الحريق والانفجار ، حسبما تم تحديدها بقرار وزير المالية'),
             (187, 'رقم 64. 667 بتاريخ 4 ربيع الآخر 1385'),
             (3542, 'ظهير شريف رقم 1.74.414 بتاريخ 20 رمضان 1394 بنشر الاتفاقية المبرمة بين المملكة المغربية'),
             (1182, 'العهد الملكي'), (1182, 'الذي أعلن عنه صاحب الجلالة الملك المعظم أيده الله')]
    assert _start_of(lines, {'title': 'ظهير شريف رقم 588-67 بتاريخ 8 شعبان 1389', 'page': 3}, 0) == 1
    assert _start_of(lines, {'title': 'الشروط النموذجية العامة للعقود المحددة بقرار وزير المالية رقم 667.64', 'page': 187}, 0) == 2
    convention = {'title': 'الاتفاقية المبرمة بين المملكة المغربية وجمهورية السينغال', 'number_as_printed': '1.74.414', 'page': 3542}
    assert _start_of(lines, convention, 0) == 4
    charter = {'title': 'العهد الملكي الذي أعلن عنه صاحب الجلالة الملك المعظم أيده الله', 'page': 1182, 'section': 'general'}
    assert _start_of(lines, charter, 0) == 5
    assert _start_of(lines, {**charter, 'section': 'other'}, 0) is None
    # A number listed apart and not printed: the title finds it; a number the contents cut short still matches as printed.
    more = lines + [(9636, 'اتفاقية التعاون القضائي والقانوني في المواد المدنية والتجارية والجزائية'),
                    (437, 'قرار رقم 2009- 733 صادر في 18 من محرم 1430')]
    agreement = {'title': 'اتفاقية التعاون القضائي والقانوني في المواد المدنية والتجارية والجزائية', 'page': 9636,
                 'number_as_printed': '1.11.75'}
    assert _start_of(more, agreement, 0) == 7
    assert _start_of(more, {'title': 'قرار رقم 2009- 733 صادر في 18 من محرم 1430', 'page': 437}, 0) == 8


def test_a_text_found_too_far_on_does_not_hide_the_ones_listed_before_it(monkeypatch):
    from types import SimpleNamespace
    from apps.corpus.services import issue_structure as s
    lines = [(10, 'مرسوم رقم 2.80.5 بتغيير'), (11, 'قرار لوزير المالية رقم 12.80 بتاريخ'),
             (12, 'مرسوم رقم 2.80.6 بتتميم'), (13, 'نص')]
    monkeypatch.setattr(s.segment, 'issue_lines', lambda issue: lines)
    toc = [{'title': 'مرسوم رقم 2.80.6 بتتميم', 'page': 9}, {'title': 'قرار لوزير المالية رقم 12.80', 'page': 11}]
    assert s.segment_issue(SimpleNamespace(number=3000), toc) == [(2, 4), (1, 2)]


def test_the_archive_describes_the_general_texts_and_the_laws_and_keeps_the_others_for_later(monkeypatch):
    """28 Oct 2026: these are described first; a special text is cut where it stands and waits for a later allowance."""
    from types import SimpleNamespace
    from apps.corpus.management.commands.archive import general_or_law
    from apps.corpus.services import issue_structure as s
    lines = [(1, 'مرسوم رقم 2.70.1'), (1, 'المادة الأولى'), (2, 'قرار لوزير الفلاحة'), (2, 'نص'),
             (3, 'ظهير شريف رقم 1.70.2'), (3, 'الفصل الأول')]
    monkeypatch.setattr(s.texts, 'issue_lines', lambda issue: lines)          # where texts_requests looks them up
    monkeypatch.setattr(s.texts, 'segment_issue', lambda issue, toc: [(0, 2), (2, 4), (4, 6)])
    toc = [{'section': 'general', 'type': 'decree', 'title': 'مرسوم رقم 2.70.1', 'page': 1},
           {'section': 'special', 'type': 'order', 'title': 'قرار لوزير الفلاحة', 'page': 2},
           {'section': 'special', 'type': 'dahir', 'title': 'ظهير شريف رقم 1.70.2', 'page': 3}]
    requests, items = s.texts_requests(SimpleNamespace(), toc, 'claude-haiku-5-5', log=lambda m: None, prefix='k-',
                                       only=general_or_law)
    assert [r['custom_id'] for r in requests] == ['k-t0', 'k-t2']
    assert items[1]['stop'] == 'later' and items[1]['pages'] == [2, 2] and 'id' not in items[1]
    answered = s.texts_answered(items, {'k-t0': {'data': {'n': 0}, 'stop': 'end_turn', 'error': ''}})
    assert [t['stop'] for t in answered] == ['end_turn', 'later', 'missing']


def test_an_old_text_is_never_given_the_day_of_the_text_its_title_cites():
    """BO 479 of 1922: the contents gave a dahir the day of the dahir its title names (3 January 1916)."""
    from datetime import date
    from apps.corpus.services.issue_structure import cited_day
    title = ('ظهير شريف يتعلق بتفويت مقاررات المخزنية التي جرى تحديدها على الطريقة المبينة بالظهير الشريف المؤرخ بسادس '
             'وعشري صفر عام ١٣٣٤ الموافق لثالث يناير سنة ١٩١٦ الصادر في التنظيم الخصوصي لتحديد الاملاك المخزنية')
    assert cited_day(title, date(1916, 1, 3))
    assert not cited_day(title, date(1916, 1, 3), closing='وحرر بالرباط في 26 صفر 1334 الموافق 3 يناير سنة 1916')
    assert cited_day('ظهير شريف في تغيير الظهير الشريف المورخ في 9 رمضان 1331 الموافق 12 غشت 1913', date(1913, 8, 12))
    assert not cited_day('ظهير شريف في تنظيم جامعة القرويين', date(1933, 3, 31))
    assert not cited_day('ظهير شريف فى تغيير الظهير المؤرخ بسادس اغشت سنة ١٩١٨ الصادر فى تقرير', date(1918, 11, 18))
    assert cited_day('قرار وزيري في تعيين الكيفية', date(1366, 9, 15))      # a Hijri year read as Gregorian


def test_an_old_issues_bare_contents_are_never_its_texts():
    """BO 479 of 1922: the contents list the titles bare (no page, no dots); each text had been «found» on its own
    contents line and kept its title alone."""
    from apps.corpus.services.issue_structure import _start_of, contents_block
    lines = [(793, 'الجريدة الرسمية'), (793, 'فهرست'), (793, 'القسم الرسمي'),
             (793, 'ظهير شريف يتعلق بتفويت قطع الاراضي المعدة للاستعمار'),
             (793, 'قرار وزيري في تعيين رئيس المحكمة الاسرائيلية بالصويرة'),
             (793, 'القسم الغير الرسمي'), (793, 'اعلانات متنوعة'), (793, 'القسم الرسمي'),
             (793, 'ظهير شريف'), (793, 'يتعلق بتفويت قطع الاراضي المعدة للاستعمار'), (793, 'الحمد لله وحده'),
             (793, 'يعلم من كتابنا هذا'), (794, 'قرار وزيري'), (794, 'في تعيين رئيس المحكمة الاسرائيلية بالصويرة'),
             (794, 'الحمد لله وحده')]
    assert contents_block(lines) == (1, 10)
    dahir = {'title': 'ظهير شريف يتعلق بتفويت قطع الاراضي المعدة للاستعمار', 'number_as_printed': '', 'page': 793,
             'section': 'general'}
    order = {**dahir, 'title': 'قرار وزيري في تعيين رئيس المحكمة الاسرائيلية بالصويرة'}
    assert _start_of(lines, dahir, 0) == 3                       # as before, without the block: its contents line
    assert _start_of(lines, dahir, 0, contents_block(lines)) == 8
    assert _start_of(lines, order, 9, contents_block(lines)) == 12


def test_of_two_old_titles_sharing_their_first_words_each_takes_its_own_heading():
    """BO 2154 of 1954: «… المصلحة العمومية احداث مركز …» had taken the heading of «… المصلحة العمومية انشاء طريق …»."""
    from apps.corpus.services.issue_structure import _start_of
    lines = [(311, 'الحمد لله وحده'), (311, 'قرار وزيري'),
             (311, 'في الاعلان أنه من المصلحة العمومية انشاء طريق وصل رقم 1 بين الطريق الثانوية'), (311, 'ان الصدر الاعظم'),
             (312, 'الحمد لله وحده'), (312, 'قرار وزيري'),
             (312, 'في الاعلان أنه من المصلحة العمومية احداث مركز لتلقي اشارات السير بواسطة الراديو'), (312, 'ان الصدر الاعظم')]
    road = {'title': 'قرار وزيري في الاعلان أنه من المصلحة العمومية انشاء طريق وصل رقم 1 بين الطريق الثانوية',
            'number_as_printed': '', 'page': 0, 'section': 'general'}
    radio = {**road, 'title': 'قرار وزيري في الاعلان أنه من المصلحة العمومية احداث مركز لتلقي اشارات السير بواسطة الراديو'}
    assert _start_of(lines, radio, 0) == 5
    assert _start_of(lines, road, 0) == 1
