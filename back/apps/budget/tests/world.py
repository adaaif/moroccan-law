"""A finance law as the corpus holds it once its BO issue is read and cut (process_issue): the issue's pages as the model
wrote them (tables in Markdown), the law's text and its articles: the balance, the posts, the articles that state each
table's amount in figures. The balance is law 50.25's (2026) as printed; each annexed table is cut down to a few lines
that still add up to the balance's own figures, so all 31 of its checks pass, as they do for the real law."""
from datetime import date

from django.utils import timezone

from apps.budget.tests.test_extract import BALANCE_2026
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Document, Edition, Issue, Page

HEAD = 'الجريدة الرسمية عدد 7465 مكرر – 9 رجب 1447 (30 ديسمبر 2025)'

# Printed pages 99 to 104. The law's text runs from page 100 to page 103: page 99 ends the text before it and page 104
# starts the next one, each with a table of its own that is not the law's.
PAGES = [
    '\n'.join([HEAD, 'ملحق بالنص السابق', '**الجدول - ب -**', '| 1.2.1.1.0.99.000 | سطر من نص سابق | 5 000 000 |']),
    '\n'.join([HEAD, 'يحدد مبلغ نفقات التسيير وفق الجدول المرفق.',
               '**الجـدول - ب -**',                # the letters stretched as printed
               '| الفصول | الوزارات أو المؤسسات | اعتمادات الأداء |',
               '|---|---|---|',
               '| | وزارة العدل | |',
               '| 1.2.1.1.0.06.000 | الموظفون والأعوان | 4 120 912 000 |',
               '| 1.2.1.2.0.06.000 | المعدات والنفقات المختلفة | 879 088 000 |',
               '| | وزارة الصحة والحماية الاجتماعية | |',
               '| 1.2.1.1.0.12.000 | الموظفون والأعوان | 200 000 000 000 |']),
    '\n'.join([HEAD,
               '| 1.2.1.3.0.13.000 | التكاليف المشتركة - التسيير | 142 490 689 000 |',
               '| | مجموع الجدول «ب» | 347 490 689 000 |',
               'الجدول «ج»',
               '| الفصول | الوزارات أو المؤسسات | اعتمادات الأداء | اعتمادات الالتزام | المجموع |',
               '|---|---|---|---|---|',
               '| 1.2.2.2.0.06.000 | وزارة العدل | 1 000 000 000 | 500 000 000 | 1 500 000 000 |',
               # Read the other way round (total, commitment, payment): its own sum says so.
               '| 1.2.2.2.0.12.000 | قطاع الصحة | 9 000 000 000 | 3 000 000 000 | 6 000 000 000 |']),
    '\n'.join([HEAD,
               '| 1.2.2.2.0.20.000 | وزارة التجهيز والماء | 2 000 000 000 | | 2 000 000 000 |',
               '| 1.2.2.4.0.13.000 | الاستثمار - النفقات الطارئة والمخصصات الاحتياطية | 127 106 794 000 |',
               '| | مجموع الجدول «ج» | 136 106 794 000 | 3 500 000 000 | 139 606 794 000 |',
               'الجدول «د»',
               '| 1.3.1.1.0.13.000 | فوائد وعمولات الدين العمومي | 44 050 556 000 |',
               '| 1.3.1.2.0.13.000 | استهلاكات الدين العمومي | 64 166 376 000 |',
               'الجدول «هـ»',
               '| 3.2.1.1.0.06.001 | مركز نشر المعلومة القانونية | 1 738 331 000 |']),
    '\n'.join([HEAD,
               'الجدول «و»',
               '| 3.2.2.2.0.12.001 | المركز الاستشفائي الإقليمي | 257 133 000 | 42 867 000 | 300 000 000 |',
               'الجدول «ز»',
               '| 4.1.0.0.0.13.001 | صندوق دعم التماسك الاجتماعي | 167 488 686 000 |']),
    '\n'.join([HEAD, 'نص موال', 'الجدول «د»', '| 1.3.1.1.0.99.000 | سطر من نص موال | 7 000 000 |']),
]

POSTS = """تحدث برسم ميزانية السنة المالية مناصب مالية جديدة.
يتم إحداث 36.395 منصبا ماليا برسم الميزانية العامة، موزعة كما يلي :
1 - 36.000 منصب مالي موزعة على الوزارات والمؤسسات كما يلي :
| الوزارات أو المؤسسات | عدد المناصب المالية |
|---|---|
| وزارة العدل ........ | 1.000 |
| وزارة الصحة و الحماية الاجتماعية | 30.000 |
| - قطاع الصحة | 20.000 |
| وزارة الداخلية | 5.000 |
| **المجموع** | **36.000** |
2 - 395 منصبا ماليا يوزعها رئيس الحكومة، لتوزيع 395 منصبا على مختلف الوزارات والمؤسسات.
وتحول 120 منصب مالي إلى وزارة الداخلية لتسوية وضعية أعوانها ........ 120"""

# The balance article names table B in its first line: it states no table's amount all the same.
BALANCE = BALANCE_2026.strip().replace('(بالدرهم) :', '(بالدرهم)، ويفصل الجدول «ب» ما يخص كل وزارة :', 1)

# (label, number, body, heading path). Article 41 names two tables and comes first: neither takes its amount.
ARTICLES = [
    ('المادة الأولى', '1', 'تستمر الجهات المختصة في تحصيل الرسوم الجمركية خلال السنة المالية 2026، وفي إحداث رسوم جديدة.',
     ['الجزء الأول', 'الباب الأول', 'الباب الثاني', 'الرسوم الجمركية']),       # a part within a part: the innermost
    ('المادة 20', '20', POSTS, ['الجزء الأول', 'الباب الثاني', 'مناصب مالية']),
    ('المادة 37', '37', BALANCE, ['الجزء الأول', 'الباب الثالث', 'الفرع الأول']),
    ('المادة 38', '38', 'تقدر المداخيل المبينة في الجدول «أ» الملحق بهذا القانون بمبلغ (421.325.037.000) درهم.',
     ['الجزء الثاني', 'الموارد']),
    ('المادة 41', '41', 'تحدد موارد ونفقات مرافق الدولة المسيرة بصورة مستقلة المبينة في الجدول «هـ» والجدول «و» في '
     '(1.995.464.000) درهم.', []),
    ('المادة 42', '42', 'يحدد مبلغ نفقات التسيير المبينة في الجدول «ب» الملحق بهذا القانون في (347.490.689.000) درهم.', []),
    ('المادة 43', '43', 'يحدد مبلغ اعتمادات الأداء واعتمادات الالتزام المبينة في الجدول «ج» في (139.606.794.000) درهم، '
     'منها (136.106.794.000) درهم اعتمادات الأداء.', []),
    ('المادة 44', '44', 'يحدد مبلغ نفقات الدين العمومي المبينة في الجدول «د» في (108.216.932.000) درهم.',
     ['الجزء الثاني', 'الفصل الأول']),
    ('المادة 45', '45', 'يحدد مبلغ نفقات الاستغلال المبينة في الجدول «هـ» في (1.738.331.000) درهم.', []),
    ('المادة 46', '46', 'يحدد مبلغ نفقات الاستثمار المبينة في الجدول «و» في (300.000.000) درهم، منها (257.133.000) '
     'درهم اعتمادات الأداء.', []),
    ('المادة 47', '47', 'يحدد مبلغ نفقات الحسابات الخصوصية للخزينة المبينة في الجدول «ز» في (167.488.686.000) درهم.', []),
    ('المادة 50', '50', 'يمكن تحويل اعتمادات بين فصول الجدول «ب» في حدود (1.000.000.000) درهم.', []),
]

URI = '/akn/ma/act/loi/50-25'


def bulletin(pages: list[str], *, number: int = 7465, suffix: str = 'bis', first: int = 99) -> Issue:
    """The issue as read: one Page row a printed page, its reading in `text`."""
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{number}{suffix}'.ljust(64, '0'),
                                  path=f'issues/bo_ar/BO_{number}{"-" + suffix if suffix else ""}_ar.pdf',
                                  mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now(),
                                  page_count=len(pages))
    Page.objects.bulk_create(Page(document=doc, index=i, printed_number=first + i, kind='scan', text=text,
                                  text_source='ocr') for i, text in enumerate(pages))
    return Issue.objects.create(edition=Edition.GENERAL_AR, number=number, suffix=suffix, date=date(2025, 12, 31),
                                document=doc, first_page_number=first)


def finance_text(issue: Issue | None, articles=ARTICLES, *, uri: str = URI, number: str = '50-25',
                 printed: str = '50.25', kind: str = 'law', title: str = 'قانون المالية رقم 50.25 للسنة المالية 2026',
                 pages: str = '100-103', page: int | None = 100) -> Text:
    """The text with two versions: as first cut (its first article only, its first page) and, newest, as it stands
    with every article: the figures come from the newest."""
    text = Text.objects.create(akn_uri=uri, type=kind, number=number, number_as_printed=printed, title_ar=title,
                               promulgating_dahir='1.25.105' if issue else '', first_published_in=issue,
                               signed_on=date(2025, 12, 27) if issue else None)
    first = Version.objects.create(text=text, language='ar', valid_from=date(2025, 12, 31), source_pages='100-100',
                                   consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=first, order=1, label='المادة الأولى', number='1', eid='art_1', printed_page=page,
                           body='نص أول.', heading_path=['الجزء الأول', 'أحكام أولى'])
    newest = Version.objects.create(text=text, language='ar', valid_from=date(2026, 7, 1), source_pages=pages,
                                    consolidation=Consolidation.MACHINE)
    Article.objects.bulk_create(
        Article(version=newest, order=n, label=label, number=num, eid=f'art_{num}', body=body, heading_path=path,
                printed_page=page) for n, (label, num, body, path) in enumerate(articles, 1))
    return text


def law_2026() -> Text:
    return finance_text(bulletin(PAGES))
