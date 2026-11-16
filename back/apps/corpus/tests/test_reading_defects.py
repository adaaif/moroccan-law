"""Reading defects found by the investigation of 19 Oct 2026, put right on the 20th: a text with no article of its own
read whole, a rubric taken from the contents for a text their reading missed, a dahir heading the scan broke, and two
texts that shared one address parted."""
import datetime
import json

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.corpus.models import Alias, Article, Text, Version
from apps.corpus.services import recut
from apps.corpus.services.issue_structure import issue_lines, load_texts, segment_issue, split_articles
from apps.sources.models import Document, Edition, Issue, Page

pytestmark = pytest.mark.django_db


def _item(kind, printed, title, front, articles=(), tail='', page=883, rubric='', preamble=(), dahir=''):
    data = {'found': True, 'type': kind, 'number_as_printed': printed, 'title': title,
            'signed_on_gregorian': '2026-01-22', 'signed_on_hijri': '', 'authority': '', 'promulgating_dahir': dahir,
            'preamble': list(preamble), 'closing': '', 'signatories': [], 'cites': [], 'amends': []}
    toc = {'type': kind, 'number_as_printed': printed, 'title': title, 'signed_on_gregorian': '2026-01-22',
           'signed_on_hijri': '', 'rubric': rubric, 'section': 'special', 'page': page}
    return {'data': data, 'toc': toc, 'pages': [page, page + 1], 'front': front, 'tail': tail,
            'articles': [{'heading_path': [], 'page': page, **a} for a in articles]}


def _issue(number, day, pages=(), tmp_path=None, first=1):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{number:064d}', path=f'BO_{number}_ar.pdf',
                                  mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now(),
                                  page_count=len(pages))
    for i, text in enumerate(pages):
        Page.objects.create(document=doc, index=i, printed_number=first + i, text=text)
    return Issue.objects.create(edition=Edition.GENERAL_AR, number=number, date=day, document=doc, first_page_number=first)


COURT = _item('decision', '261.26 م.د', 'قرار رقم 261.26 م.د صادر في 2 من شعبان 1447 (22 يناير 2026).',
              'قرار رقم 261.26 م.د صادر في 2 من شعبان 1447 (22 يناير 2026)\nالحمد لله وحده،\nالمحكمة الدستورية،\n'
              'بعد اطلاعها على رسالة الإحالة ؛\nوبناء على الدستور ؛\nحيث إن المادة 4 من القانون المحال تنص على ما يلي :',
              [{'label': 'المادة 4', 'body': '«يتألف المجلس من تسعة عشر عضوا.»'}],
              'وصدر بمقر المحكمة الدستورية بالرباط في 22 يناير 2026.\nالإمضاءات :\nمحمد أمين بنعبد الله.',
              rubric='المحكمة الدستورية', preamble=['وبناء على الدستور ؛'])


def test_a_court_decision_is_read_whole_visas_and_all_never_cut_at_the_articles_it_quotes():
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7479, date=datetime.date(2026, 2, 2))
    load_texts(issue, [COURT])
    version = Version.objects.get(text__akn_uri='/akn/ma/act/decision/2026/261-26')
    (whole,) = version.articles.all()
    assert whole.label == '' and whole.eid == 'art_1' and version.preamble == ''
    assert whole.body.startswith('الحمد لله وحده،\nالمحكمة الدستورية،\nبعد اطلاعها')
    assert 'المادة 4\n«يتألف المجلس' in whole.body and 'وصدر بمقر' not in whole.body


def test_a_licence_with_no_article_and_an_opinion_on_a_bill_are_their_own_words():
    licence = _item('decision', '1260.25', 'مقرر للأمين العام للحكومة يرخص للسيدة ريم بلافريج بحمل صفة مهندس معماري',
                    'بموجب مقرر للأمين العام للحكومة رقم 1260.25 صادر في\n16 من ذي القعدة 1446 (14 ماي 2025) يرخص '
                    'للسيدة ريم بلافريج أن تحمل\nصفة مهندس معماري.\nالإذن بممارسة الهندسة المعمارية.',
                    rubric='الإذن بممارسة الهندسة المعمارية.')
    opinion = _item('other', '97.15', 'رأي المجلس الاقتصادي والاجتماعي والبيئي بشأن مشروع القانون التنظيمي رقم 97.15',
                    'رأي المجلس الاقتصادي والاجتماعي والبيئي\nبشأن مشروع القانون التنظيمي رقم 97.15\n'
                    'توصل المجلس بإحالة من السيد رئيس مجلس النواب.',
                    [{'label': 'المادة الأولى', 'body': 'يحدد هذا القانون التنظيمي شروط ممارسة حق الإضراب.'}],
                    'ملاحق\nملحق 1: لائحة أعضاء اللجنة\n| 1. عضو |', page=7233)
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7413, date=datetime.date(2025, 6, 2))
    load_texts(issue, [licence, opinion])
    (one,) = Article.objects.filter(version__text__number_as_printed='1260.25')
    assert one.body.startswith('بموجب مقرر') and one.body.endswith('صفة مهندس معماري.')      # the next rubric is not its
    whole, annex = Article.objects.filter(version__text__number_as_printed='97.15').order_by('order')
    assert whole.label == '' and whole.body.endswith('المادة الأولى\nيحدد هذا القانون التنظيمي شروط ممارسة حق الإضراب.')
    assert annex.number == 'annex' and annex.label == 'ملحق 1: لائحة أعضاء اللجنة'


def test_a_law_its_entry_did_not_name_takes_its_rubric_from_the_contents_not_the_entrys():
    # BO 7213: the model read the contents' first four lines after «فهرست» and dropped them, so 01.23's entry
    # (rubric «أكاديمية الحسن الثاني…») held law 83.21, which went by that rubric and 01.23's dahir.
    contents = ('الشركات الجهوية متعددة الخدمات.\nظهير شريف رقم 1.23.53 صادر في 23 من ذي الحجة 1444 (12 يوليو 2023) '
                'بتنفيذ القانون رقم 83.21 المتعلق بالشركات الجهوية متعددة الخدمات ........ 5697\nفهرست\n'
                'أكاديمية الحسن الثاني للعلوم والتقنيات.\nظهير شريف رقم 1.23.56 صادر في 23 من ذي الحجة 1444 (12 يوليو 2023) '
                'بتغيير وتتميم الظهير الشريف المعتبر بمثابة قانون رقم 1.93.364')
    issue = _issue(7213, datetime.date(2023, 7, 17), [contents, 'ظهير شريف رقم 1.23.56', 'قانون رقم 83.21'], first=5695)
    host = _item('law', '01.23', 'ظهير شريف رقم 1.23.56 صادر في 23 من ذي الحجة 1444 (12 يوليو 2023) بتغيير وتتميم '
                 'الظهير الشريف المعتبر بمثابة قانون رقم 1.93.364', 'ظهير شريف رقم 1.23.56\nقانون رقم 83.21\n'
                 'يتعلق بالشركات الجهوية متعددة الخدمات', [{'label': 'المادة الأولى', 'body': 'تحدث شركات.', 'page': 5697}],
                 page=5696, rubric='أكاديمية الحسن الثاني للعلوم والتقنيات.', dahir='1.23.56')
    load_texts(issue, [host])
    law = Text.objects.get(akn_uri='/akn/ma/act/loi/83-21')
    assert law.rubric == 'الشركات الجهوية متعددة الخدمات.' and law.first_published_page == 5697
    assert law.promulgating_dahir == '' and not Alias.objects.filter(alias='/akn/ma/act/dahir/1-23-56').exists()


PAGES_7228 = [
    'فهرست\nظهير شريف رقم 1.23.69 صادر في 23 من محرم 1445 (10 أغسطس 2023) بتنفيذ القانون رقم 58.22 ........ 7160',
    ('ظهير شريف رقم 1.23.69 صادر في 23 من محرم 1445 (10 أغسطس 2023) بتنفيذ القانون رقم 58.22 بتغيير القانون رقم 41.05.\n'
     'الحمد لله وحده،\nوحرر بالرباط في 23 من محرم 1445 (10 أغسطس 2023).\nقانون رقم 58.22\nالمادة الأولى\n'
     'تغير المادة 2 من القانون رقم 41.05.\nالمادة 2\nيدخل هذا القانون حيز التنفيذ.'),
    ('ظهيرشريف رقم 1.23.70 صادرفي 23 من محرم 1445 (10 أ\nرقم 11.23 المتعلق بتنفيذ قانون المالية\nالحمد للّه وحده،\n'
     'قانون التصفية رقم 11.23\nالمتعلق بتنفيذ قانون المالية للسنة المالية 2021\nالمــادة 1\n'
     'تحدد مبالغ النتائج النهائية لتنفيذ ميزانية سنة 2021.\nالمــادة 2\nتحدد الموارد وفق الجدول «ب».\n'
     'الجدول "ب" (المادة 3)\n| الموارد | 352.999.326.817,36 |'),
]
TOC_7228 = [{'section': 'general', 'rubric': 'هيئات التوظيف الجماعي للرأسمال.', 'type': 'dahir', 'number_as_printed': '1.23.69',
             'title': 'ظهير شريف رقم 1.23.69 صادر في 23 من محرم 1445 (10 أغسطس 2023) بتنفيذ القانون رقم 58.22',
             'signed_on_gregorian': '2023-08-10', 'signed_on_hijri': '', 'page': 7160}]


def test_a_dahir_whose_heading_the_scan_broke_is_found_by_its_laws_own_heading(tmp_path, settings):
    # BO 7228: «ظهيرشريف … صادرفي … (10 أ» named no law, so the 2021 settlement law and its 150,000 letters of tables
    # stood as law 58.22's last article and annex.
    settings.CORPUS_DIR = tmp_path
    issue = _issue(7228, datetime.date(2023, 9, 7), PAGES_7228, first=7159)
    work = tmp_path / 'reports' / 'issues' / issue.key
    work.mkdir(parents=True)
    (work / 'toc.json').write_text(json.dumps(TOC_7228, ensure_ascii=False))
    span = segment_issue(issue, TOC_7228)[0]
    cut = split_articles(issue_lines(issue)[span[0]:span[1]])
    host = {**_item('law', '58.22', '', cut['front'], page=7160, dahir='1.23.69'), 'toc': TOC_7228[0],
            'articles': cut['articles'], 'tail': cut['tail']}
    (work / 'texts.json').write_text(json.dumps([host], ensure_ascii=False))
    load_texts(issue, [host])
    assert Article.objects.filter(version__text__akn_uri='/akn/ma/act/loi/58-22', number='annex').exists()   # the fault

    recut.repair(issue, log=lambda *a: None)
    settlement = Text.objects.get(akn_uri='/akn/ma/act/loi/11-23')
    assert settlement.title_ar.startswith('قانون التصفية رقم 11.23')
    assert [a.number for a in Article.objects.filter(version__text=settlement)] == ['1', '2', 'annex']
    own = Article.objects.filter(version__text__akn_uri='/akn/ma/act/loi/58-22')
    assert [a.number for a in own] == ['1', '2'] and own.last().body == 'يدخل هذا القانون حيز التنفيذ.'
    # texts.json keeps the repair: the host's tail was the settlement law's, and a reload must not give it back.
    saved = json.loads((work / 'texts.json').read_text())
    assert saved[0]['tail'] == '' and saved[-1]['stop'] == 'recut'
    load_texts(issue, saved)
    assert not Article.objects.filter(version__text__akn_uri='/akn/ma/act/loi/58-22', number='annex').exists()


def test_two_texts_that_shared_one_address_are_parted_when_their_issues_load_again(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    court_issue = _issue(7479, datetime.date(2026, 2, 2))
    order_issue = _issue(7489, datetime.date(2026, 3, 9))
    order = _item('decision', '261.26', 'قرار لوزير التعليم العالي رقم 261.26 بتحديد بعض المعادلات بين الشهادات',
                  'قرار لوزير التعليم العالي رقم 261.26 بتحديد بعض المعادلات بين الشهادات',
                  [{'label': 'المادة الأولى', 'body': 'تقبل لمعادلة الماستر الشهادة التالية.'},
                   {'label': 'المادة الثانية', 'body': 'ينشر هذا القرار بالجريدة الرسمية.'}], page=1560)
    for issue, item in ((court_issue, COURT), (order_issue, order)):
        work = tmp_path / 'reports' / 'issues' / issue.key
        work.mkdir(parents=True)
        (work / 'texts.json').write_text(json.dumps([item], ensure_ascii=False))
    # The state an old loader left: one row, the court's title, both issues' versions, the minister's shown last.
    shared = Text.objects.create(akn_uri='/akn/ma/act/decision/2026/261-26', type='decision', number='261-26',
                                 title_ar=COURT['data']['title'], first_published_in=court_issue)
    for issue in (court_issue, order_issue):
        Version.objects.create(text=shared, language='ar', valid_from=issue.date, consolidation='as_published',
                               source_document=issue.document)

    call_command('reload_issues', write=True, stdout=open('/dev/null', 'w'))
    court = Text.objects.get(akn_uri='/akn/ma/act/decision/2026/261-26')
    assert court.pk == shared.pk and court.versions.get().source_document == court_issue.document
    assert court.versions.get().articles.get().body.startswith('الحمد لله وحده،')
    # The minister's «قرار لوزير» is an order, at its order's address (R18 of the road plan).
    minister = Text.objects.get(akn_uri='/akn/ma/act/arrete/261-26')
    assert minister.type == 'order' and minister.versions.get().articles.count() == 2
    assert minister.first_published_in == order_issue


def test_a_decree_heading_cut_before_its_date_is_named_up_to_its_number():
    # The columns broke the heading («… رقم 2.21.605 صادر في 1»); the cut kept its articles (it had thrown on 6763).
    head = {'kind': 'decree', 'printed': '2.21.605', 'number': '2-21-605', 'gregorian': '', 'hijri': '', 'dahir': '',
            'page': 4410, 'line': 0, 'words': 'مرسوم رقم 2.21.605 صادر في 1'}
    part = [(4410, 'مرسوم رقم 2.21.605 صادر في 1'), (4410, 'رئيس الحكومة،'), (4410, 'المادة الأولى'),
            (4410, 'تحدد لائحة المؤسسات.'), (4410, 'المادة الثانية'), (4410, 'ينشر هذا المرسوم بالجريدة الرسمية.')]
    item = recut._item(None, head, part)
    assert item['toc']['title'] == 'مرسوم رقم 2.21.605' and [a['label'] for a in item['articles']] == ['المادة الأولى', 'المادة الثانية']


def test_a_text_with_no_article_is_cut_from_its_own_heading_not_from_the_law_before_it():
    # BO 7180: organic law 48.22's entry began at 14.22's dahir; both have a «مادة فريدة», and 48.22 had taken
    # the decree after it for its articles until the recut gave them back.
    front = ('ظهير شريف رقم 1.23.37 صادر في 23 من شعبان 1444 (16 مارس 2023)\nقانون تنظيمي رقم 14.22\nمادة فريدة\n'
             'تغير وتتمم أحكام المواد 6 و10 من القانون التنظيمي رقم 106.13.\n'
             'ظهير شريف رقم 1.23.38 صادر في 23 من شعبان 1444 (16 مارس 2023) بتنفيذ القانون التنظيمي رقم 48.22\n'
             'قانون تنظيمي رقم 48.22\nيقضي بتغيير وتتميم القانون التنظيمي رقم 02.12\nمادة فريدة\n'
             'يغير ويتمم الملحق رقم 2 المرفق بالقانون التنظيمي رقم 02.12.')
    item = _item('law', '14.22', '', front, page=4385, dahir='1.23.37')
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7180, date=datetime.date(2023, 3, 23))
    load_texts(issue, [item])
    (one,) = Article.objects.filter(version__text__akn_uri='/akn/ma/act/loi-organique/48-22')
    assert one.label == 'مادة فريدة' and one.body.startswith('يغير ويتمم الملحق رقم 2')


def test_a_heading_a_corrigendum_quotes_is_not_cut_as_a_text(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    pages = ['فهرست\nاستدراك خطإ ........ 120',
             ('استدراك خطإ وقع بالجريدة الرسمية عدد 6746 بتاريخ 17 من جمادى الأولى 1440 (24 يناير 2019)، الصفحة 112\n'
              'قرار لوزير الفلاحة والصيد البحري رقم 3770.18 صادر في 5 ربيع الآخر 1440 (13 ديسمبر 2018) يقضي بتسليم قطعة فلاحية.\n'
              'بدلا من :\nالمادة الأولى\nتسلم السيدة فاطمة القطعة الفلاحية.\nيقرأ :\nالمادة الأولى\nتسلم السيدة فاطمة القطعة الفلاحية رقم 5.')]
    issue = _issue(6753, datetime.date(2019, 2, 18), pages, first=119)
    work = tmp_path / 'reports' / 'issues' / issue.key
    work.mkdir(parents=True)
    toc = [{'section': 'general', 'rubric': '', 'type': 'other', 'number_as_printed': '', 'title': 'استدراك خطإ',
            'signed_on_gregorian': '', 'signed_on_hijri': '', 'page': 120}]
    (work / 'toc.json').write_text(json.dumps(toc, ensure_ascii=False))
    assert [p['why'] for p in recut.plan(issue)] == ['quoted by a corrigendum']


def test_a_reload_sweeps_an_older_runs_text_only_when_its_words_stand_in_one_it_wrote(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    issue = _issue(7509, datetime.date(2026, 5, 18))
    words = 'يعاد ترتيب الممر المستوي رقم 2021 عند النقطة الكيلومترية 178+117 الناتج عن تقاطع الطريق العمومية مع خط السكة.'
    order = _item('order', '580.26', 'قرار لوزير النقل واللوجيستيك رقم 580.26 بإعادة ترتيب الممر المستوي', 'قرار لوزير النقل',
                  [{'label': 'المادة الأولى', 'body': words}], page=6100)
    work = tmp_path / 'reports' / 'issues' / issue.key
    work.mkdir(parents=True)
    (work / 'texts.json').write_text(json.dumps([order], ensure_ascii=False))
    # An older run's rows: a merged «Multiple texts» holding the order's words, and an order its texts.json lost.
    for uri, body in (('/akn/ma/act/texte/2026/654-26', words), ('/akn/ma/act/arrete/1842-26', 'يرخص بإحداث مصيدة. ' * 8)):
        t = Text.objects.create(akn_uri=uri, type='other', first_published_in=issue)
        v = Version.objects.create(text=t, language='ar', valid_from=issue.date, consolidation='as_published',
                                   source_document=issue.document)
        Article.objects.create(version=v, order=1, label='المادة الأولى', body=body)
    call_command('reload_issues', '7509', write=True, stdout=open('/dev/null', 'w'))
    assert not Text.objects.filter(akn_uri='/akn/ma/act/texte/2026/654-26').exists()
    assert Text.objects.filter(akn_uri='/akn/ma/act/arrete/1842-26').exists()
    assert Text.objects.filter(akn_uri='/akn/ma/act/arrete/580-26').exists()


def test_a_text_loaded_after_its_neighbours_takes_the_address_of_its_own_place():
    """The Bulletin-from-No.-1 review: an unnumbered text's address is its position among the issue's texts; loaded later
    on its own (the archive's MISSING), it never takes the address of the text loaded before it."""
    first = _item('decision', '', 'قرار لوزير المالية في تعيين مساعدين فنيين', 'قرار لوزير المالية في تعيين مساعدين فنيين\nنص أول.')
    second = _item('decision', '', 'قرار لوزير الفلاحة في توقيف صيد الشابل', 'قرار لوزير الفلاحة في توقيف صيد الشابل\nنص ثان.')
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=2266, date=datetime.date(1956, 3, 30))
    load_texts(issue, [first, second], only={0})
    load_texts(issue, [first, second], only={1})
    titles = dict(Text.objects.values_list('akn_uri', 'title_ar'))
    assert titles['/akn/ma/act/decision/1956-03-30/bo2266-1'].startswith('قرار لوزير المالية')
    assert titles['/akn/ma/act/decision/1956-03-30/bo2266-2'].startswith('قرار لوزير الفلاحة')


def test_the_1913_print_of_a_code_held_from_adala_is_its_first_print_never_its_words():
    """H7 of the Bulletin-from-No.-1 review: the DOC's dahir of 12 August 1913, unnumbered as every dahir then, is the code
    the site holds from Adala: its title and words stay, its first print becomes the 1913 issue's page."""
    doc = Text.objects.create(akn_uri='/akn/ma/act/code/doc', type='dahir', title_ar='ظهير بمثابة قانون الالتزامات والعقود')
    Version.objects.create(text=doc, language='ar', valid_from=datetime.date(2019, 1, 1), consolidation='adala')
    item = _item('dahir', '', 'ظهير شريف بمثابة قانون الالتزامات والعقود', 'ظهير شريف\nبمثابة قانون الالتزامات والعقود',
                 [{'label': 'الفصل 1', 'body': 'الالتزامات تنشأ عن الاتفاقات.'}], page=73)
    item['data']['signed_on_gregorian'] = '1913-08-12'
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=46, date=datetime.date(1913, 9, 12))
    assert load_texts(issue, [item])['held'] == 1
    doc.refresh_from_db()
    assert (doc.first_published_in_id, doc.first_published_page, doc.signed_on) == (issue.pk, 73, datetime.date(1913, 8, 12))
    assert doc.title_ar == 'ظهير بمثابة قانون الالتزامات والعقود' and Text.objects.count() == 1
