"""The links pipeline (rows L3–L10 of the links review), on wordings taken from the BO."""
import datetime

import pytest

from apps.consolidation.models import Change, Doubt
from apps.consolidation.services import engine
from apps.consolidation.services.instructions.amending import read
from apps.consolidation.services.instructions.dates import in_force, lead_date
from apps.consolidation.services.instructions.provisions import clauses
from apps.corpus.models import Article, Mention, Status, Text, Version
from apps.sources.models import Edition, Issue
from apps.sources.services import coverage

pytestmark = pytest.mark.django_db

ART_24 = ('يدخل هذا القانون حيز التنفيذ فور تعيين المدير العام للوكالة وانعقاد مجلسها الإداري.\n'
          'وابتداء من نفس التاريخ تنسخ جميع المقتضيات التشريعية المخالفة لهذا القانون، لا سيما :\n'
          '- الظهير الشريف رقم 1.93.51 الصادر في 22 من ربيع الأول 1414 (10 سبتمبر 1993) المتعلق بإحداث الوكالات الحضرية ؛\n'
          '- القانون رقم 19.88 المتعلق بإحداث الوكالة الحضرية لفاس وإنقاذ مدينة فاس.')


def text(uri, kind, number, title, day, articles, number_issue=7533, preamble=''):
    issue, _ = Issue.objects.get_or_create(edition=Edition.GENERAL_AR, number=number_issue, suffix='',
                                           defaults={'date': day})
    t = Text.objects.create(akn_uri=uri, type=kind, number=number, number_as_printed=number.replace('-', '.'),
                            title_ar=title, first_published_in=issue, first_published_page=5100)
    v = Version.objects.create(text=t, language='ar', valid_from=day, consolidation='as_published', preamble=preamble)
    for n, (label, body) in enumerate(articles, 1):
        Article.objects.create(version=v, order=n, label=label, number=str(n), eid=f'art_{n}', body=body, printed_page=5105)
    return t


def test_a_repeal_on_a_condition_waits_for_it():
    law = text('/akn/ma/act/loi/64-23', 'law', '64-23', 'قانون رقم 64.23 يتعلق بإحداث الوكالات الجهوية للتعمير والإسكان',
               datetime.date(2026, 8, 10), [('المادة 24', ART_24)])
    engine.run([law], log=lambda *_: None)
    old = Text.objects.get(akn_uri='/akn/ma/act/loi/19-88')          # waiting: cited, not read yet
    change = Change.objects.get(text_uri=old.akn_uri, source='reading')
    assert change.verb == 'repealed' and change.number == '' and change.effective_on is None
    assert change.effective_rule == 'condition' and 'تعيين المدير العام' in change.effective_words
    stand = engine.standing(old)
    assert stand['status'] != Status.REPEALED and stand['repeal_pending']['rule'] == 'condition'
    assert 'فور تعيين' in engine.standing(law)['in_force_when']


def test_a_repeal_on_publication_repeals_and_a_title_that_amends_is_against_it():
    old = text('/akn/ma/act/decret/2-10-385', 'decree', '2-10-385', 'مرسوم رقم 2.10.385 بتنظيم صنع وتسويق الخل',
               datetime.date(2011, 6, 1), [('المادة 1', 'نص.')], number_issue=5950)
    new = text('/akn/ma/act/decret/2-24-100', 'decree', '2-24-100', 'مرسوم رقم 2.24.100 يتعلق بالجودة والسلامة الصحية للخل',
               datetime.date(2024, 3, 1), [('المادة 16', 'تدخل مقتضيات هذا المرسوم حيز التنفيذ ابتداء من تاريخ نشره في الجريدة '
                                           'الرسمية.\nينسخ ابتداء من هذا التاريخ المرسوم رقم 2.10.385 الصادر في 23 من جمادى '
                                           'الآخرة 1432 (27 ماي 2011) بتنظيم صنع وتسويق الخل.')], number_issue=7280)
    engine.run([new], log=lambda *_: None)
    old.refresh_from_db()
    assert old.status == Status.REPEALED
    assert engine.standing(old)['repealed']['by_uri'] == new.akn_uri
    # «ينسخ الجدولان … الملحقان بالمرسوم»: a part of the text, never the whole of it.
    assert read('ينسخ الجدولان رقم 1 و2 الملحقان بالمرسوم السالف الذكر رقم 2.77.68.').action == 'unclear'
    amender = text('/akn/ma/act/decret/2-24-616', 'decree', '2-24-616', 'مرسوم رقم 2.24.616 بتغيير المرسوم رقم 2.10.385',
                   datetime.date(2024, 7, 25), [('المادة 2', 'ينسخ المرسوم رقم 2.10.385 الصادر في 23 من جمادى الآخرة 1432.')],
                   number_issue=7320)
    engine.run([amender], log=lambda *_: None)
    c = Change.objects.get(by_uri=amender.akn_uri, source='reading')
    assert c.witnesses.get('title') is False and c.state == Change.State.CONFLICT


def test_an_old_dahir_named_by_its_day_is_amended_and_two_of_a_day_are_told_apart_by_their_words():
    """H9 of the Bulletin-from-No.-1 review: before 1956 a text names the one it amends by its day; of two dahirs signed that
    day, the words after the citation pick one, and words that pick none give no target (never a guess)."""
    def old(uri, title, day, issue):
        t = text(uri, 'dahir', '', title, day, [('الفصل 3', 'نص قديم.')], number_issue=issue)
        Text.objects.filter(pk=t.pk).update(signed_on=day, number_as_printed='')
        return t
    day = datetime.date(1922, 4, 11)
    fishing = old('/akn/ma/act/dahir/1922-05-02/bo470-1', 'ظهير شريف في الصيد في الأنهار والبحيرات', day, 470)
    old('/akn/ma/act/dahir/1922-05-02/bo470-2', 'ظهير شريف في تنظيم مصلحة البريد والتلغراف', day, 470)
    amender = text('/akn/ma/act/dahir/1935-08-09/bo1189-1', 'dahir', '', 'ظهير شريف في تغيير الظهير الشريف الصادر في 12 شعبان 1340',
                   datetime.date(1935, 8, 9), [('فصل فريد', 'يغير على النحو التالي الفصل 3 من الظهير الشريف الصادر في 12 شعبان '
                                               '1340 (11 أبريل 1922) المتعلق بالصيد في الأنهار والبحيرات :\n«الفصل 3. - نص جديد.»')],
                   number_issue=1189)
    engine.run([amender], log=lambda *_: None)
    c = Change.objects.get(by_uri=amender.akn_uri, source='reading')
    assert c.text_uri == fishing.akn_uri and c.number == '3'
    from apps.corpus.services import works
    assert works.resolve_dated('dahir', '1922-04-11', 'بشأن مسائل أخرى') == ('', 'ambiguous')


def test_an_order_never_repeals_a_law_nor_the_law_its_object_was_taken_under():
    law = text('/akn/ma/act/loi/77-15', 'law', '77-15', 'قانون رقم 77.15 يقضي بمنع صنع الأكياس من مادة البلاستيك',
               datetime.date(2015, 12, 7), [('المادة 1', 'نص.')], number_issue=6422)
    repeal = ('ينسخ القرار المشترك لوزير الصناعة والتجارة والاستثمار والاقتصاد الرقمي ووزير الفلاحة والصيد البحري '
              'رقم 1798.16 الصادر في 14 من رمضان 1437 (20 يونيو 2016) بتطبيق أحكام المادة الثانية من المرسوم رقم '
              '2.16.174 الصادر في 25 من جمادى الآخرة 1437 (4 أبريل 2016) بتطبيق بعض أحكام القانون رقم 77.15 القاضي '
              'بمنع صنع الأكياس من مادة البلاستيك.')
    assert read(repeal).action == 'unclear' and read(repeal).reason == 'repeal_object'
    assert read('ينسخ القرار رقم 1309.77 الصادر في 9 أكتوبر 1977.').reason == 'whole_text'
    order = text('/akn/ma/act/arrete/493-23', 'order', '493-23', 'قرار مشترك بتطبيق مقتضيات المادة الثانية من المرسوم رقم 2.16.174',
                 datetime.date(2023, 4, 24), [('المادة الخامسة', 'ينسخ القانون رقم 77.15 القاضي بمنع صنع الأكياس.')],
                 number_issue=7189)
    engine.run([order], log=lambda *_: None)
    c = Change.objects.get(by_uri=order.akn_uri, source='reading')
    assert c.state == Change.State.UNCLEAR and c.witnesses == {'rank': False}
    law.refresh_from_db()
    assert law.status != Status.REPEALED


def test_a_change_waits_for_its_text_and_is_applied_when_it_arrives():
    amending = text('/akn/ma/act/loi/13-26', 'law', '13-26', 'قانون رقم 013.26 بتغيير وتتميم القانون رقم 2.00',
                    datetime.date(2026, 8, 10), [('المادة الأولى', 'تغير وتتمم، على النحو التالي، أحكام المادة 8 من القانون '
                                                  'رقم 2.00 :\n«المادة 8. - لا تشمل الحماية الجديدة ما يلي.»')])
    engine.run([amending], log=lambda *_: None)
    change = Change.objects.get(source='reading')
    assert change.text_uri == '/akn/ma/act/loi/2-00' and change.placed is None
    assert change.detail['waiting'] == 'no_base' and change.state == Change.State.READ
    Text.objects.filter(akn_uri='/akn/ma/act/loi/2-00').delete()      # the waiting row, filled by the issue that comes
    base = text('/akn/ma/act/loi/2-00', 'law', '2-00', 'القانون رقم 2.00 المتعلق بحقوق المؤلف', datetime.date(2000, 5, 18),
                [('المادة 8', 'لا تشمل الحماية ما يلي.')], number_issue=4796)
    Article.objects.filter(version__text=base).update(number='8', eid='art_8')
    engine.run([base], log=lambda *_: None)
    change.refresh_from_db()
    assert change.placed is True
    machine = base.versions.get(consolidation='machine')
    assert machine.valid_from == datetime.date(2026, 8, 10)
    assert machine.articles.get(number='8').body == 'لا تشمل الحماية الجديدة ما يلي.'


def test_dates_of_force_and_an_articles_own_date():
    assert in_force('ينشر هذا القرار بالجريدة الرسمية ويعمل به ابتداء من فاتح سبتمبر 2021.').on == datetime.date(2021, 9, 1)
    after = engine.takes_effect(in_force('يدخل هذا المرسوم حيز التنفيذ بعد ستة أشهر من تاريخ نشره.'), datetime.date(2024, 3, 31))
    assert after[0] == datetime.date(2024, 9, 30) and after[1] == 'after'
    # The first of the month after publication (law 02.24), and a delay counted from it.
    first = in_force('مع مراعاة أحكام المواد من 7 إلى 12 أعلاه، تدخل أحكام هذا القانون حيز التنفيذ ابتداء من فاتح الشهر '
                     'الموالي لتاريخ نشره بالجريدة الرسمية.')
    assert engine.takes_effect(first, datetime.date(2025, 3, 3))[:2] == (datetime.date(2025, 4, 1), 'after')
    later = in_force('يدخل هذا القانون حيز التنفيذ بعد انقضاء اثني عشر شهرا، تحتسب ابتداء من فاتح الشهر الموالي للشهر '
                     'الذي تم فيه نشر هذا القانون بالجريدة الرسمية.')
    assert engine.takes_effect(later, datetime.date(2025, 3, 3))[:2] == (datetime.date(2026, 4, 1), 'after')
    law = text('/akn/ma/act/loi/50-25', 'law', '50-25', 'قانون المالية رقم 50.25 للسنة المالية 2026', datetime.date(2025, 12, 22),
               [('المادة 6', 'ابتداء من فاتح يناير 2026، تغير وتتمم أحكام المادة 5 من القانون رقم 12.34 كما يلي:\n'
                             '«المادة 5. - نص جديد.»')], number_issue=7465)
    engine.run([law], log=lambda *_: None)
    c = Change.objects.get(source='reading')
    assert c.effective_on == datetime.date(2026, 1, 1) and c.effective_rule == 'stated'


def test_citations_are_kept_by_article_and_a_decree_applies_a_laws_article():
    law = text('/akn/ma/act/loi/31-13', 'law', '31-13', 'قانون رقم 31.13 يتعلق بالحق في الحصول على المعلومات',
               datetime.date(2018, 3, 12), [('المادة 1', 'نص.'), ('المادة 2', 'نص.')], number_issue=6655)
    decree = text('/akn/ma/act/decret/2-18-500', 'decree', '2-18-500', 'مرسوم رقم 2.18.500 بتطبيق القانون رقم 31.13',
                  datetime.date(2018, 9, 1), [('المادة 1', 'وفق مقتضيات المادة 2 من القانون رقم 31.13، تحدد اللجنة …')],
                  number_issue=6700, preamble='بناء على القانون رقم 31.13 المتعلق بالحق في الحصول على المعلومات، ولا سيما المادة 2 منه؛')
    engine.run([decree], log=lambda *_: None)
    cites = Mention.objects.get(from_uri=decree.akn_uri, from_eid='art_1', kind='cites')
    assert (cites.to_uri, cites.to_number, cites.state) == (law.akn_uri, '2', 'resolved')
    assert set(Mention.objects.filter(kind='applies', to_uri=law.akn_uri).values_list('to_number', flat=True)) == {'', '2'}
    # «الفصل 155 من الدستور»: never a decision that happens to be numbered 155.
    assert clauses('نص لا يحيل إلى شيء.') == []


def test_a_models_reading_alone_is_never_fact():
    amending = text('/akn/ma/act/loi/66-19', 'law', '66-19', 'قانون رقم 66.19 بتغيير القانون رقم 2.00',
                    datetime.date(2022, 6, 20), [('المادة الأولى', 'تغير بعض أحكام القانون رقم 2.00 بطريقة لا تقرأ بالرمز.')],
                    number_issue=7101)
    Change.objects.create(text_uri='/akn/ma/act/loi/2-00', number='8', verb='modified', source='model', by_kind='law',
                          by_number='66-19', by_uri=amending.akn_uri, by_article='المادة الأولى', wording=['نص.'],
                          published_on=datetime.date(2022, 6, 20), effective_on=datetime.date(2022, 6, 20),
                          detail={'by_model': True})
    engine.run([amending], log=lambda *_: None)
    c = Change.objects.get(source='reading', by_uri=amending.akn_uri)
    assert c.detail['by_model'] and c.state == Change.State.UNCLEAR


def test_coverage_counts_the_issues_read_and_names_the_missing(settings, tmp_path):
    import json
    settings.CORPUS_DIR = tmp_path
    runs = tmp_path / 'reports' / 'runs'
    runs.mkdir(parents=True)
    (runs / 'queue_2019_2026.txt').write_text('7535 2026-08-17 u\n7534 2026-08-13 u\n7533 2026-08-10 u\n7533-bis 2026-08-11 u\n')
    for key, entries in (('7533', [{'toc': {'type': 'law', 'title': 'قانون'}, 'data': {'found': True}},
                                   {'toc': {'type': 'decree', 'title': 'مرسوم لم يوجد'}, 'data': None}]),
                         ('7533-bis', [{'toc': {'type': 'other', 'title': 'تقرير سنوي'}, 'data': None}]),
                         ('7535', [{'toc': {'type': 'law', 'title': 'قانون'}, 'data': {'found': True}}])):
        (tmp_path / 'reports' / 'issues' / key).mkdir(parents=True)
        (tmp_path / 'reports' / 'issues' / key / 'texts.json').write_text(json.dumps(entries))
    text('/akn/ma/act/loi/64-23', 'law', '64-23', 'قانون', datetime.date(2026, 8, 10), [('المادة 1', 'نص.')])
    text('/akn/ma/act/loi/1-26', 'law', '1-26', 'قانون', datetime.date(2026, 8, 17), [('المادة 1', 'نص.')], number_issue=7535)
    coverage.refresh()
    led = coverage.ledger(fresh=True)
    # 7533-bis lists only a report: read with no text. 7534 was never gone through.
    assert led['known'] == 4 and led['read'] == 3 and [m['key'] for m in led['missing']] == ['7534']
    since = coverage.since(datetime.date(2026, 8, 9))
    assert [m['key'] for m in since['missing']] == ['7534'] and since['unfound'] == 1
    assert coverage.since(datetime.date(2010, 1, 1))['before']


def test_coverage_reaches_back_to_1956_with_the_archive_and_counts_decisions_not_read(settings, tmp_path):
    """Z23 of the second-archive-run review: an old issue counts as read once its laws, general texts, special decrees
    and orders are; the decisions it lists and the site has not read yet are counted apart."""
    import json
    settings.CORPUS_DIR = tmp_path
    runs = tmp_path / 'reports' / 'runs'
    runs.mkdir(parents=True)
    (runs / 'queue_2019_2026.txt').write_text('7533 2026-08-10 u\n')
    assert coverage.since(datetime.date(1990, 1, 1))['before']          # no archive yet: 2019 is the first day
    (runs / 'queue_1956_2018.txt').write_text('4000 1990-03-01 archive\n4001 1990-03-08 archive\n4002 1990-03-15 archive\n')
    later = {'stop': 'later', 'data': None}
    for key, entries in (('4000', [{'toc': {'type': 'law', 'section': 'general', 'title': 'قانون'}, 'data': {'found': True}},
                                   {'toc': {'type': 'decision', 'section': 'special', 'title': 'قرار بتعيين'}, **later}]),
                         ('4001', [{'toc': {'type': 'order', 'section': 'special', 'title': 'قرار لوزير'}, **later}]),
                         ('7533', [{'toc': {'type': 'law', 'title': 'قانون'}, 'data': {'found': True}}])):
        (tmp_path / 'reports' / 'issues' / key).mkdir(parents=True)
        (tmp_path / 'reports' / 'issues' / key / 'texts.json').write_text(json.dumps(entries))
    text('/akn/ma/act/loi/7-90', 'law', '7-90', 'قانون', datetime.date(1990, 3, 1), [('المادة 1', 'نص.')], number_issue=4000)
    text('/akn/ma/act/loi/64-23', 'law', '64-23', 'قانون', datetime.date(2026, 8, 10), [('المادة 1', 'نص.')])
    coverage.refresh()
    since = coverage.since(datetime.date(1990, 2, 1))
    # 4001's special order waits: not read. 4002 was never gone through. 4000 is read, its decision waits.
    assert [m['key'] for m in since['missing']] == ['4001', '4002'] and since['waiting'] == 1
    assert coverage.since(datetime.date(1950, 1, 1))['before'] and coverage.since(None)['from'] == datetime.date(1956, 1, 1)


def test_an_archive_text_says_it_was_read_from_scans_and_counts_the_issues_unread_after_it(api, settings, tmp_path):
    """UX3 of the phone-test review: a 1990 text read from its scan says so, and its answer counts the 45 issues
    printed after it that the site has not read, naming only the first 40 (a 1964 decree's list was 111 KB)."""
    import json
    from apps.sources.models import Document
    settings.CORPUS_DIR = tmp_path
    runs = tmp_path / 'reports' / 'runs'
    runs.mkdir(parents=True)
    (runs / 'queue_2019_2026.txt').write_text('7533 2026-08-10 u\n')
    (runs / 'queue_1956_2018.txt').write_text(''.join(
        f'{4000 + i} 1990-{3 + i // 28:02d}-{1 + i % 28:02d} archive\n' for i in range(46)))
    for key in ('4000', '7533'):         # read: the text's own issue and the newest; the 45 between never gone through
        (tmp_path / 'reports' / 'issues' / key).mkdir(parents=True)
        (tmp_path / 'reports' / 'issues' / key / 'texts.json').write_text(json.dumps(
            [{'toc': {'type': 'law', 'section': 'general', 'title': 'قانون'}, 'data': {'found': True}}]))
    t = text('/akn/ma/act/loi/7-90', 'law', '7-90', 'قانون', datetime.date(1990, 3, 1), [('المادة 1', 'نص.')],
             number_issue=4000)
    from django.utils import timezone
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='4000' * 16, path='BO_4000_ar.pdf',
                                  mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now(),
                                  page_count=12, meta={'archive': True})
    Version.objects.filter(text=t).update(source_document=doc)
    coverage.refresh()
    d = api.get('/api/corpus/at/ma/loi/7-90/').json()
    c = d['standing']['coverage']
    assert c['missing_count'] == 45 and len(c['missing']) == 40 and c['partial'] and c['missing'][0]['key'] == '4001'
    assert d['version']['read_from_scans']
    Document.objects.filter(pk=doc.pk).update(meta={})
    assert not api.get('/api/corpus/at/ma/loi/7-90/').json()['version']['read_from_scans']


def test_coverage_reaches_back_to_no_1_once_the_queue_holds_the_years_before_1956(settings, tmp_path):
    """H10 of the Bulletin-from-No.-1 review: the archive's queue holds 1913–1955 once the plan's coverage_from says so;
    its first day is then the site's first."""
    settings.CORPUS_DIR = tmp_path
    runs = tmp_path / 'reports' / 'runs'
    runs.mkdir(parents=True)
    (runs / 'queue_1956_2018.txt').write_text('2254 1956-01-06 archive\n')
    assert coverage.start() == datetime.date(1956, 1, 1)
    (runs / 'queue_1956_2018.txt').write_text('1 1913-02-01 archive\n2254 1956-01-06 archive\n')
    assert coverage.start() == datetime.date(1913, 2, 1)
    assert not coverage.since(datetime.date(1930, 1, 1))['before']


def test_a_bare_article_in_an_amending_article_links_to_the_amended_text(api):
    base = text('/akn/ma/act/loi/2-00', 'law', '2-00', 'القانون رقم 2.00', datetime.date(2000, 5, 18),
                [('المادة 8', 'نص.')], number_issue=4796)
    Article.objects.filter(version__text=base).update(number='8', eid='art_8')
    amending = text('/akn/ma/act/loi/66-19', 'law', '66-19', 'قانون رقم 66.19 بتغيير القانون رقم 2.00',
                    datetime.date(2022, 6, 20), [('المادة الأولى', 'تغير وتتمم، على النحو التالي، أحكام المادة 8 من '
                                                  'القانون رقم 2.00 :\n«المادة 8. - نص جديد يحيل إلى المادة 8.»')],
                    number_issue=7101)
    engine.run([amending], log=lambda *_: None)
    r = api.get('/api/corpus/at/ma/loi/66-19/?window=40')
    assert r.status_code == 200
    hrefs = [m.get('href') for m in r.json()['articles'][0]['marks']]
    assert '/ma/loi/2-00/art_8' in hrefs


def test_a_repeal_in_stages_goes_whole_from_its_last_date():
    # The minimum-wage decrees (T4 of the work plan): one sector from January, the other from April.
    staged = ('تنسخ ابتداء من فاتح يناير 2025، فيما يخص النشاطات غير الفلاحية، وابتداء من فاتح أبريل 2025، فيما يخص '
              'النشاطات الفلاحية، مقتضيات المرسوم رقم 2.23.799 الصادر في 27 من ربيع الأول 1445 (13 أكتوبر 2023).')
    ins = read(staged)
    assert ins.action == 'repeal' and ins.reason == 'whole_text' and ins.target['number'] == '2-23-799'
    assert lead_date(staged) == datetime.date(2025, 4, 1)
    assert lead_date('ابتداء من فاتح يناير 2022، تغير المادة 5.') == datetime.date(2022, 1, 1)


def test_a_decrees_legal_basis_links_it_to_the_article_it_applies():
    # T1 of the work plan: «ولا سيما المادة 43 منه» in the first visa past the Constitution makes the notice decree the
    # one that applies art. 43; «بتطبيق المادة 356 من القانون رقم 65.99» makes the wage decree apply art. 356; a
    # decree the site holds only from Adala has its visas read too.
    from apps.corpus.models import Mention
    code = text('/akn/ma/act/loi/65-99', 'law', '65-99', 'القانون رقم 65.99 المتعلق بمدونة الشغل',
                datetime.date(2003, 12, 8), [('المادة 43', 'نص.')], number_issue=5167)
    Article.objects.filter(version__text=code).update(number='43', eid='art_43')
    wage = text('/akn/ma/act/decret/2-25-983', 'decree', '2-25-983', 'مرسوم رقم 2.25.983 بتحديد مبلغ الحد الأدنى القانوني للأجر',
                datetime.date(2025, 12, 29), [('المادة الأولى', 'يحدد في 17,92 درهما.')], number_issue=7469,
                preamble='بناء على الدستور، ولا سيما الفصل 90 منه\nوعلى المرسوم رقم 2.08.374 الصادر في 5 رجب 1429 (9 يوليو 2008) '
                         'بتطبيق المادة 356 من القانون رقم 65.99 المتعلق بمدونة الشغل')
    notice = Text.objects.create(akn_uri='/akn/ma/act/decret/2-04-469', type='decree', number='2-04-469',
                                 number_as_printed='2.04.469', title_ar='مرسوم يتعلق بأجل الإخطار', signed_on=datetime.date(2004, 12, 9))
    Version.objects.create(text=notice, language='ar', valid_from=datetime.date(2005, 1, 3), consolidation='adala',
                           preamble='بناء على القانون رقم 65.99 المتعلق بمدونة الشغل ولا سيما المادة 43 منه')
    engine.run([wage, notice], log=lambda *_: None)
    applies = set(Mention.objects.filter(kind='applies').values_list('from_uri', 'to_uri', 'to_number'))
    assert applies == {('/akn/ma/act/decret/2-25-983', '/akn/ma/act/loi/65-99', '356'),
                       ('/akn/ma/act/decret/2-04-469', '/akn/ma/act/loi/65-99', '43')}


def test_a_sentence_that_names_the_entry_into_force_does_not_set_it():
    # Law 07.20 (H5 of the housing plan): its art. 7 mentions «قبل دخول هذا القانون حيز التنفيذ»; art. 6 sets the date.
    assert in_force('لا تطبق الجزاءات عن عدم الإقرار قبل دخول هذا القانون حيز التنفيذ.') is None
    assert in_force('تعتبر الديون تلك التي ظلت غير مستخلصة إلى غاية دخول هذا القانون حيز التنفيذ.') is None
    assert in_force('يدخل هذا القانون حيز التنفيذ ابتداء من فاتح يناير 2021.').rule == 'stated'


def test_a_doc_article_cited_turned_around_or_by_the_dahirs_date_is_the_docs():
    # Law 41.25 (BO 7526, H1 of the housing plan): «الفصل 3-618 من الظهير الشريف الصادر في 9 رمضان 1331 … بمثابة
    # قانون الالتزامات والعقود» is the DOC's 618-3; «ظهير 9 رمضان 1331 … المتعلق بالتحفيظ العقاري» is no dahir «9».
    ins = read('تغير على النحو التالي، أحكام الفصل 3-618 من الظهير الشريف الصادر في 9 رمضان 1331 (12 أغسطس 1913) '
               'بمثابة قانون الالتزامات والعقود :\n«الفصل 3-618. - يجب أن يرد عقد البيع الابتدائي في محرر رسمي.»')
    assert ins.target == {'code': 'doc'} and [u.number for u in ins.units] == ['618-3']
    ins = read('تنسخ أحكام الفصل 17-618 من الظهير الشريف الصادر في 9 رمضان 1331 (12 أغسطس 1913) بمثابة قانون '
               'الالتزامات والعقود.')
    assert ins.target == {'code': 'doc'} and [n['number'] for n in ins.articles] == ['618-17']
    ins = read('يغير الفصل 65 من ظهير 9 رمضان 1331 (12 أغسطس 1913) المتعلق بالتحفيظ العقاري كما يلي :\n«الفصل 65. - نص.»')
    assert ins.target == {'code': 'land_registration'}


def test_a_change_an_official_consolidation_already_holds_raises_no_doubt():
    from django.utils import timezone

    from apps.consolidation.models import Doubt
    from apps.sources.models import Document
    day = datetime.date(2026, 8, 24)
    base = text('/akn/ma/act/decret/2-10-421', 'decree', '2-10-421', 'المرسوم رقم 2.10.421 بشأن المركبات',
                datetime.date(2010, 9, 30), [('المادة 8', 'نص قديم.')], number_issue=5878)
    Article.objects.filter(version__text=base).update(number='8', eid='art_8')
    amending = text('/akn/ma/act/decret/2-24-393', 'decree', '2-24-393', 'مرسوم رقم 2.24.393 بتغيير المرسوم رقم 2.10.421',
                    day, [('المادة الأولى', 'تغير وتتمم، على النحو التالي، أحكام المادة 9 من المرسوم رقم 2.10.421 :\n'
                                            '«المادة 9. - نص جديد.»')], number_issue=7537)
    engine.run([amending], log=lambda *_: None)
    assert Doubt.objects.filter(text_uri=base.akn_uri, by_uri=amending.akn_uri).exists()       # no article 9 to change
    # Adala's consolidation of the same day holds it: readers see its wording, and the machine's failure is no doubt.
    doc = Document.objects.create(source='adala', kind='consolidated_text', sha256='b' * 64, path='v.pdf', bytes=1,
                                  mime='application/pdf', page_count=1, fetched_at=timezone.now(),
                                  meta={'as_of': day.isoformat()})
    v = Version.objects.create(text=base, language='ar', valid_from=day, consolidation='adala', source_document=doc)
    Article.objects.create(version=v, order=1, label='المادة 9', number='9', eid='art_9', body='نص جديد.')
    engine.run([base], log=lambda *_: None)
    assert not Doubt.objects.filter(text_uri=base.akn_uri, by_uri=amending.akn_uri, status='open').exists()
    assert Change.objects.get(source='reading', text_uri=base.akn_uri).detail.get('covered') is True


def test_a_person_gives_the_wording_whose_dots_the_machine_cannot_place():
    # The health review, S3: 27.22 rewrote 65.00 art. 2 keeping «موظفو» where 2002 printed «موظفي»; the dots stand
    # on no anchor. A resolved «unplaced» doubt carries the article whole (apply_wordings), and the version is built.
    from apps.consolidation.models import Doubt
    amo = text('/akn/ma/act/loi/65-00', 'law', '65-00', 'قانون رقم 65.00 بمثابة مدونة التغطية الصحية الأساسية',
               datetime.date(2002, 11, 21), [('المادة 1', 'يسري التأمين على :\n- موظفي وأعوان الدولة ؛\n- الأجراء.')],
               number_issue=5058)
    law = text('/akn/ma/act/loi/27-22', 'law', '27-22', 'قانون رقم 27.22 بتغيير وتتميم القانون رقم 65.00',
               datetime.date(2022, 11, 30), [('المادة الأولى', 'تغير أحكام المادة 1 من القانون السالف الذكر رقم 65.00 :\n'
                                                            '«المادة 1. - تستفيد الفئات التالية :\n«- موظفو وأعوان............ ؛\n'
                                                            '«- المستقلون.»')], number_issue=7147)
    engine.run([law], log=lambda *_: None)
    assert not amo.versions.filter(consolidation='machine').exists()
    Doubt.objects.create(text_uri=amo.akn_uri, number='1', by_uri=law.akn_uri, reason=Doubt.Reason.UNPLACED,
                         status=Doubt.Status.RESOLVED, detail={'wording': ['تستفيد الفئات التالية :', '- موظفو وأعوان الدولة ؛',
                                                                          '- المستقلون.']})
    engine.run([law], log=lambda *_: None)
    v = amo.versions.get(consolidation='machine')
    assert v.articles.get().body.splitlines()[1] == '- موظفو وأعوان الدولة ؛'
    change = Change.objects.get(text_uri=amo.akn_uri, source='reading')
    assert change.state == 'checked' and change.detail['worded'] and change.wording[1].startswith('- موظفو وأعوان..')


def test_a_condition_a_person_dated_stands_in_force_from_that_day():
    # 65.00 art. 147 (S3): in force once the texts installing the funds' bodies were published (BO 5344, 18 Aug 2005).
    from apps.consolidation.models import Doubt
    amo = text('/akn/ma/act/loi/65-00', 'law', '65-00', 'قانون رقم 65.00 بمثابة مدونة التغطية الصحية الأساسية',
               datetime.date(2002, 11, 21), [('المادة 147', 'تدخل أحكام هذا القانون حيز التنفيذ، ابتداء من تاريخ النشر '
                                                        'بالجريدة الرسمية للنصوص التطبيقية اللازمة لتنصيب أجهزة الوكالة.')])
    assert 'in_force_when' in engine.standing(amo)
    Doubt.objects.create(text_uri=amo.akn_uri, by_uri=amo.akn_uri, reason=Doubt.Reason.WHEN, status=Doubt.Status.RESOLVED,
                         detail={'on': '2005-08-18', 'because': 'BO 5344'})
    stand = engine.standing(amo)
    assert stand['status'] == Status.IN_FORCE and stand['in_force_since'] == datetime.date(2005, 8, 18)


def test_a_repeal_names_a_decrees_articles_by_their_ordinal_words():
    # Decree 2.26.551 art. 2 repeals the passport decree's temporary passport: «المادتين السابعة والثامنة».
    ins = read('تُنسخ أحكام المادتين السابعة والثامنة من المرسوم السالف الذكر رقم 2.08.310.')
    assert ins.action == 'repeal' and [a['number'] for a in ins.articles] == ['7', '8']
    # A paragraph's ordinal is not an article's.
    assert [a['number'] for a in read('تغير أحكام المادة 12 الفقرة الثانية من القانون رقم 36.21 كما يلي :\n«المادة 12. - نص.»').articles] == ['12']


def test_an_official_text_keeps_its_words_and_an_amendment_read_from_the_archive_waits_for_a_person():
    # 28 Oct 2026: decree 2.05.734's articles had become Haiku's reading of the decree that amended them
    # («أداوه» for «أداؤه»), over Adala's words. A text with an official consolidation keeps it; what the archive's scans
    # say changes it is shown as found, not applied. A text only the BO printed takes it as before.
    from django.utils import timezone

    from apps.sources.models import Document

    def document(source, kind, sha, meta):
        return Document.objects.create(source=source, kind=kind, sha256=sha * 64, path='x.pdf', bytes=1, language='ar',
                                       mime='application/pdf', page_count=1, fetched_at=timezone.now(), meta=meta)
    official = text('/akn/ma/act/decret/2-05-734', 'decree', '2-05-734', 'مرسوم رقم 2.05.734', datetime.date(2005, 8, 18),
                    [('المادة 8', 'نص قديم.')], number_issue=5344)
    adala = Version.objects.create(text=official, language='ar', valid_from=datetime.date(2014, 11, 20),
                                   consolidation='adala', source_document=document('adala', 'consolidated_text', 'a', {}))
    Article.objects.create(version=adala, order=1, label='المادة 8', number='8', eid='art_8', body='نص أداؤه.')
    printed = text('/akn/ma/act/decret/2-60-104', 'decree', '2-60-104', 'مرسوم رقم 2.60.104', datetime.date(1960, 3, 4),
                   [('المادة 8', 'نص قديم.')], number_issue=2471)
    Article.objects.filter(version__text__in=[official, printed]).update(number='8', eid='art_8')
    amending = text('/akn/ma/act/decret/2-14-707', 'decree', '2-14-707', 'مرسوم رقم 2.14.707 بتغيير مرسومين',
                    datetime.date(2015, 1, 5),
                    [('المادة الأولى', 'تغير وتتمم، على النحو التالي، أحكام المادة 8 من المرسوم رقم 2.05.734 :\n'
                                       '«المادة 8. - نص أداوه.»'),
                     ('المادة الثانية', 'تغير وتتمم، على النحو التالي، أحكام المادة 8 من المرسوم رقم 2.60.104 :\n'
                                        '«المادة 8. - نص جديد.»')], number_issue=6330)
    Issue.objects.filter(number=6330).update(document=document('sgg', 'bo_issue', 'c', {'archive': '2015/BO_6330_Ar.pdf'}))
    engine.run([amending], log=lambda *_: None)
    engine.run([official, printed], log=lambda *_: None)
    held = Change.objects.get(source='reading', text_uri=official.akn_uri)
    assert held.detail['waiting'] == 'official' and held.placed is None
    assert not official.versions.filter(consolidation='machine').exists()
    assert official.latest_version().pk == adala.pk
    assert printed.latest_version().consolidation == 'machine'
    assert printed.latest_version().articles.get(number='8').body == 'نص جديد.'


def test_a_code_named_by_an_old_text_is_the_code_of_its_day():
    # 28 Oct 2026: law 72.03 (2004) amends «قانون المسطرة المدنية», the dahir of 1974; read without its date, the
    # change went to law 58.25 (2026), and a 1958 dahir's repeal made the new civil procedure «repealed».
    from apps.corpus.services import works
    new = text('/akn/ma/act/loi/58-25', 'law', '58-25', 'قانون رقم 58.25 يتعلق بالمسطرة المدنية',
               datetime.date(2026, 2, 23), [('المادة 185', 'نص جديد.')], number_issue=7485)
    old = text('/akn/ma/act/dahir/1-74-447', 'dahir', '1-74-447', 'ظهير شريف بمثابة قانون رقم 1.74.447 بالمصادقة على نص قانون المسطرة المدنية',
               datetime.date(1974, 9, 30), [('الفصل 185', 'نص قديم.')], number_issue=3230)
    Article.objects.filter(version__text__in=[new, old]).update(number='185', eid='art_185')
    amending = text('/akn/ma/act/loi/72-03', 'law', '72-03', 'قانون رقم 72.03 بتغيير وتتميم قانون المسطرة المدنية',
                    datetime.date(2004, 2, 5), [('المادة الأولى', 'تغير وتتمم، على النحو التالي، أحكام الفصل 185 من قانون '
                                                'المسطرة المدنية :\n«الفصل 185. - نص معدل.»')], number_issue=5184)
    engine.run([amending], log=lambda *_: None)
    assert set(Change.objects.filter(source='reading').values_list('text_uri', flat=True)) == {old.akn_uri}
    # A name cited before its code's own year names no text rather than today's code.
    assert works.code_address('criminal_procedure', datetime.date(1980, 1, 1)) == ''
    assert works.code_address('criminal_procedure', datetime.date(2010, 1, 1)) == '/akn/ma/act/loi/22-01'
    assert works.code_address('civil_procedure') == '/akn/ma/act/loi/58-25'
    assert works.number_year('22-01') == '2001' and works.number_year('1-59-413') == '1959'


def test_a_consolidation_counts_what_was_read_since_its_own_day(api, settings, tmp_path):
    """HM26 of the hard-moment review: the Labour Code (2003), held only as Adala's 2026 consolidation, said
    «صدر قبل 1913», as every text held only as a consolidation did."""
    import json
    from apps.corpus.models import Consolidation, Text, Version
    settings.CORPUS_DIR = tmp_path
    runs = tmp_path / 'reports' / 'runs'
    runs.mkdir(parents=True)
    (runs / 'queue_2019_2026.txt').write_text('7533 2026-08-10 u\n')
    (tmp_path / 'reports' / 'issues' / '7533').mkdir(parents=True)
    (tmp_path / 'reports' / 'issues' / '7533' / 'texts.json').write_text(json.dumps(
        [{'toc': {'type': 'law', 'title': 'قانون'}, 'data': {'found': True}}]))
    t = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', title_ar='القانون رقم 65.99 المتعلق بمدونة الشغل')
    Version.objects.create(text=t, language='ar', valid_from=datetime.date(2026, 7, 16), consolidation=Consolidation.ADALA)
    coverage.refresh()
    c = api.get('/api/corpus/at/ma/loi/65-99/').json()['standing']['coverage']
    assert not c['before'] and c['from'] == '2026-07-16' and c['latest']['key'] == '7533'


@pytest.mark.django_db
def test_in_force_is_said_for_a_reason():
    """RD6 of the readers review: «نافذ» for an official portal's copy and for a text printed since 2019; of an older text
    as printed the page says «لم نجد ما ينسخه», however many issues were read after it."""
    from apps.corpus.models import Text, Version
    from apps.corpus.services.links import text_links

    def said(uri, signed, kind):
        text = Text.objects.create(akn_uri=uri, type='dahir', number=uri.rsplit('/', 1)[-1], title_ar='ظهير', signed_on=signed)
        Version.objects.create(text=text, language='ar', valid_from=signed, consolidation=kind)
        return text_links(text)['standing']['sure']

    assert said('/akn/ma/act/dahir/1941-09-05/bo1506-6', datetime.date(1941, 8, 5), 'as_published') is False
    assert said('/akn/ma/act/decision/2014/1808-14', datetime.date(2014, 5, 5), 'as_published') is False
    assert said('/akn/ma/act/loi/59-24', datetime.date(2026, 10, 1), 'as_published') is True
    assert said('/akn/ma/act/dahir/1-59-413', datetime.date(1962, 11, 26), 'adala') is True        # the penal code, Adala's copy


def test_an_articles_changes_are_read_against_the_copy_shown():
    """RD2 of the readers review: a change the official copy already holds is not «found and not applied», and one whose
    words the copy does not hold is said missing."""
    from types import SimpleNamespace

    from apps.consolidation.services.history import settled
    day = datetime.date
    sgg = SimpleNamespace(consolidation='sgg', valid_from=day(2021, 5, 17), source_document_id=1,
                          source_document=SimpleNamespace(meta={'as_of': '2023-11-29'}))
    table = {'16': [
        {'on': day(2016, 1, 25), 'state': 'read', 'placed': False, 'waiting': 'official', 'effective_on': day(2016, 1, 25), 'rule': ''},
        {'on': day(2026, 1, 29), 'state': 'read', 'placed': False, 'waiting': None, 'effective_on': day(2026, 1, 29), 'rule': ''},
        {'on': day(2026, 1, 29), 'state': 'read', 'placed': False, 'waiting': None, 'effective_on': day(2027, 2, 1), 'rule': ''},
        {'on': day(2026, 1, 29), 'state': 'doubt', 'placed': False, 'waiting': None, 'effective_on': day(2026, 1, 29), 'rule': ''}]}
    old, new, coming, doubted = settled(table, sgg, today=day(2026, 11, 9))['16']
    assert (old['waiting'], old['missing']) == (None, False)            # 2016, in a copy brought up to 2023: held
    assert new['missing'] is True                                       # 2026: not in it, and said
    assert coming['missing'] is False and doubted['missing'] is False   # not yet in force; not shown as fact
    assert table['16'][0]['waiting'] == 'official'                      # the table itself is not touched
    printed = SimpleNamespace(consolidation='as_published', valid_from=day(1977, 11, 4), source_document_id=None)
    assert settled(table, printed) is table                             # a text as printed says «كما نُشر»
    machine = SimpleNamespace(consolidation='machine', valid_from=day(2021, 4, 5), source_document_id=None)
    assert settled(table, machine, today=day(2026, 11, 9))['16'][0]['missing'] is True     # the batch held back


def _day(clause, published):
    return engine.takes_effect(in_force(clause), published)[:2]


def test_a_day_counted_from_publication_is_computed():
    """RD3 of the readers review: the criminal procedure code, in every court since 2003, read «يدخل حيز التنفيذ
    حين يتحقق ما يقوله» because its clause counts months from its publication."""
    jan, d = datetime.date(2003, 1, 30), datetime.date
    assert _day('يجري العمل بمقتضيات هذا القانون ابتداء من اليوم الأول للشهر التاسع عشر الموالي لنشره بالجريدة الرسمية.',
                jan) == (d(2004, 8, 1), 'after')
    assert _day('يدخل هذا القانون حيز التنفيذ في اليوم الأول من الشهر السادس الموالي لشهر نشره في الجريدة الرسمية.',
                d(2023, 3, 9)) == (d(2023, 9, 1), 'after')
    assert _day('تدخل أحكام هذا القانون حيز التطبيق في اليوم الأول من الشهر الرابع الذي يلي شهر نشره في الجريدة الرسمية.',
                d(1993, 11, 3)) == (d(1994, 3, 1), 'after')
    assert _day('يعمل بهذا القانون ابتداء من اليوم الاول من الشهر الموالي لتاريخ نشره بالجريدة الرسمية.',
                d(1979, 12, 5)) == (d(1980, 1, 1), 'after')
    # Law 15.97: once the third month after the month that printed it has ended.
    assert _day('يدخل هذا القانون حيز التطبيق بعد انصرام الشهر الثالث الموالي للشهر الذي ينشر فيه بالجريدة الرسمية.',
                d(2000, 6, 1)) == (d(2000, 10, 1), 'after')
    assert _day('يجري العمل بمقتضيات هذا القرار في اليوم الخامس عشر التالي لنشره بالجريدة الرسمية والسلام',
                d(1937, 8, 13)) == (d(1937, 8, 28), 'after')
    assert _day('يدخل هذا القانون حيز التنفيذ في اليوم الموالي لتاريخ نشره في الجريدة الرسمية.',
                d(2011, 9, 19)) == (d(2011, 9, 20), 'after')
    # The delay said before the publication it is counted from; «بعد ثلاثة أشهر من نشره» had been read as «من نشره».
    assert _day('يدخل هذا القانون حيز التنفيذ سنة بعد تاريخ نشره في الجريدة الرسمية.', d(2016, 9, 19)) == (d(2017, 9, 19), 'after')
    assert _day('يدخل هذا المرسوم حيز التنفيذ ثلاثة (3) أشهر بعد تاريخ نشره.', d(2020, 11, 16)) == (d(2021, 2, 16), 'after')
    assert _day('يدخل هذا القانون حيز التنفيذ بعد ثلاثة أشهر من نشره بالجريدة الرسمية.', d(2011, 6, 30)) == (d(2011, 9, 30), 'after')
    assert _day('يدخل هذا القانون حيز التنفيذ بعد انصرام تسعين (90) يوما من تاريخ نشره في الجريدة الرسمية.',
                d(2026, 8, 10)) == (d(2026, 11, 8), 'after')
    # A time to comply is not the text's start, and a number the table lacks is never taken for one.
    assert _day('يدخل هذا القانون حيز التنفيذ ابتداء من تاريخ نشره، وتتم المطابقة خلال أجل لا يتعدى سنة من تاريخ نشره.',
                d(2020, 1, 6))[1] == 'publication'
    assert in_force('يدخل هذا القانون حيز التنفيذ عشرين شهرا بعد تاريخ نشره.').rule == 'condition'


def test_a_stated_day_is_the_one_the_clause_leads_to():
    d = datetime.date
    # The protectorate's spellings and «سنة» before the year; the closing formula's days are never the text's.
    old = in_force('يجري العمل بهذا القرار ابتداء من فاتح غشت سنة 1952 والسلام وحرر بالرباط في 11 رمضان 1371 موافق 4 يونيه '
                   'سنة 1952 الامضاء : محمد المقري واذن بنشره ، 11 يوليوز 1952')
    assert (old.rule, old.on) == ('stated', d(1952, 8, 1))
    assert in_force('يجري العمل بهذا القرار ابتداء من 15 يونيه سنة 1937 والسلام').on == d(1937, 6, 15)
    assert in_force('يجري العمل بهذا القرار ابتداء من رابع مارس 1948 والسلام').on == d(1948, 3, 4)
    assert in_force('يعمل بهذا القرار ابتداء من فاتح دیسمبر 1984.').on == d(1984, 12, 1)          # a Persian ye in the reading
    assert in_force('تدخل أحكام هذا القانون حيز التنفيذ في 9 رمضان 1402 (فاتح يوليو 1982).').on == d(1982, 7, 1)
    # Another text's day is not this one's: the order it repeals, the law it cites.
    assert in_force('يعمل بهذا القرار الذي يلغى القرار رقم 78.748 الصادر في 19 من رجب 1398 (26 يونيه 1978) بتعيين آمر مساعد '
                    'بالدفع ونائبه ابتداء من فاتح مارس 1980.').on == d(1980, 3, 1)
    assert in_force('يعمل بهذا القرار ابتداء من تاريخ نشره بالجريدة الرسمية، وينسخ ابتداء من نفس التاريخ قرار الوزيرة رقم '
                    '2681.19 الصادر في 23 من ذي القعدة 1440 (26 يوليو 2019) بتعيين رئيس.').rule == 'publication'
    waits = in_force('تدخل أحكام هذا القانون التنظيمي حيز التنفيذ ابتداء من اليوم الموالي لتاريخ الإعلان الرسمي عن النتائج '
                     'النهائية للانتخابات، وفقا للقانون رقم 45.08 الصادر بتنفيذه الظهير الشريف رقم 1.09.02 بتاريخ 22 من صفر '
                     '1430 (18 فبراير 2009)، برسم ميزانية 2015.')
    assert waits.rule == 'condition'
    # An end is not a start, and a mention sets nothing.
    assert in_force('يسري مفعول هذا القرار إلى غاية نهاية شهر دجنبر 2027.') is None
    assert in_force('يستمر الموظفون العاملون بالجهة في تاريخ دخول هذا القانون التنظيمي حيز التنفيذ متمتعين بجميع حقوقهم.') is None
    assert in_force('ينشر هذا القرار بالجريدة الرسمية ويعمل به.').rule == 'publication'
    # Sets it, and mentions it after: the criminal procedure code as amended.
    amended = in_force('يجري العمل بمقتضيات هذا القانون ابتداء من فاتح أكتوبر من سنة .2003 غير أن المقررات الصادرة قبل تاريخ '
                       'دخوله حيز التطبيق تظل خاضعة من حيث الطعون وآجالها للمقتضيات المضمنة في القوانين المنسوخة.')
    assert (amended.rule, amended.on) == ('stated', d(2003, 10, 1))


@pytest.mark.django_db
def test_a_commencement_clause_a_later_law_rewrote_is_read_in_the_official_copy():
    """The criminal procedure code printed «the first day of the nineteenth month after publication»; its art. 755 now
    states 1 October 2003. The old code it repeals is repealed from that day."""
    law = text('/akn/ma/act/loi/22-01', 'law', '22-01', 'قانون رقم 22.01 يتعلق بالمسطرة الجنائية', datetime.date(2003, 1, 30),
               [('المادة 755', 'يجري العمل بمقتضيات هذا القانون ابتداء من اليوم الأول للشهر التاسع عشر الموالي لنشره بالجريدة الرسمية.'),
                ('المادة 756', 'تنسخ جميع النصوص المخالفة لهذا القانون وعلى الأخص:\n1- الظهير الشريف رقم 1.58.261 بتاريخ فاتح شعبان '
                               '1378 (10 فبراير 1959) الذي يحتوي على قانون المسطرة الجنائية.')], number_issue=5078)
    assert engine.standing(law, today=datetime.date(2003, 12, 1))['status'] == Status.NOT_YET_IN_FORCE
    copy = Version.objects.create(text=law, language='ar', valid_from=datetime.date(2025, 9, 8), consolidation='adala')
    Article.objects.create(version=copy, order=1, label='المادة 755', number='755', eid='art_755',
                           body='يجري العمل بمقتضيات هذا القانون ابتداء من فاتح أكتوبر من سنة .2003 غير أن المقررات الصادرة قبل '
                                'تاريخ دخوله حيز التطبيق تظل خاضعة للمقتضيات المضمنة في القوانين المنسوخة.')
    assert engine.standing(law, today=datetime.date(2003, 12, 1))['status'] == Status.IN_FORCE
    engine.run([law], log=lambda *_: None)
    repeal = Change.objects.get(text_uri='/akn/ma/act/dahir/1-58-261', verb='repealed')
    assert repeal.effective_on == datetime.date(2003, 10, 1)


@pytest.mark.django_db
def test_a_change_printed_long_before_its_target_was_signed_is_refused():
    """RD3: law 1.13 of 2014 amends «قانون المسطرة المدنية»; the name now answers to the code of 2026, which read
    «عُدّل بعد صدوره (11)»."""
    new = text('/akn/ma/act/loi/58-25', 'law', '58-25', 'قانون رقم 58.25 يتعلق بالمسطرة المدنية', datetime.date(2026, 2, 23),
               [('المادة 1', 'تطبق أحكام هذا القانون أمام المحاكم.')], number_issue=7480)
    Text.objects.filter(pk=new.pk).update(signed_on=datetime.date(2026, 2, 11))
    old = text('/akn/ma/act/loi/1-13', 'law', '1-13', 'قانون رقم 1.13 بتغيير القانون رقم 58.25', datetime.date(2014, 3, 20),
               [('المادة الأولى', 'تغير على النحو التالي أحكام المادة 1 من القانون رقم 58.25 :\n«المادة 1. - نص آخر.»')],
               number_issue=6240)
    engine.run([old], log=lambda *_: None)
    assert not Change.objects.filter(text_uri=new.akn_uri, source='reading').exists()
    doubt = Doubt.objects.get(by_uri=old.akn_uri, reason='target_unknown')
    assert doubt.detail['why'] == 'later' and doubt.detail['target'] == {'uri': new.akn_uri}
    assert engine.standing(new)['status'] == Status.IN_FORCE
    # A year or less apart is a date read wrong more often than a wrong text: kept.
    Text.objects.filter(pk=new.pk).update(signed_on=datetime.date(2014, 9, 1))
    engine.run([old], log=lambda *_: None)
    assert Change.objects.filter(text_uri=new.akn_uri, source='reading').count() == 1


@pytest.mark.django_db
def test_a_code_held_only_as_an_official_copy_repeals_the_texts_its_final_provisions_name():
    """RD3: the family code is Adala's copy; its art. 397 repeals the personal status code of 1957."""
    old = text('/akn/ma/act/dahir/1-57-343', 'dahir', '1-57-343', 'ظهير شريف رقم 1.57.343 في شأن الأحوال الشخصية',
               datetime.date(1957, 12, 6), [('الفصل 1', 'الخطبة وعد بالزواج.')], number_issue=2354)
    code = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', number_as_printed='70.03',
                               title_ar='قانون رقم 70.03 بمثابة مدونة الأسرة', signed_on=datetime.date(2004, 2, 3))
    copy = Version.objects.create(text=code, language='ar', valid_from=datetime.date(2021, 7, 29), consolidation='adala')
    Article.objects.create(version=copy, order=1, label='المادة 397', number='397', eid='art_397',
                           body='تنسخ جميع الأحكام المخالفة لهذه المدونة أو التي قد تكون تكرارا لها، ولا سيما أحكام:\n'
                                '- الظهير الشريف رقم 1.57.343 الصادر بتاريخ 28 ربيع الثاني 1377 (22 نوفمبر 1957) المطبق بموجبه '
                                'في سائر المملكة المغربية مقتضيات الكتابين الأول والثاني.')
    Article.objects.create(version=copy, order=2, label='المادة 400', number='400', eid='art_400',
                           body='كل ما لم يرد به نص في هذه المدونة، يرجع فيه إلى المذهب المالكي.')
    engine.run([code], log=lambda *_: None)
    repeal = Change.objects.get(text_uri=old.akn_uri, verb='repealed')
    assert (repeal.number, repeal.effective_on, repeal.detail['copy']) == ('', datetime.date(2004, 2, 3), 'adala')
    old.refresh_from_db()
    assert old.status == Status.REPEALED


def test_a_school_year_that_has_begun_and_a_budget_year_are_days():
    d = datetime.date
    began = in_force('ينشر هذا القرار بالجريدة الرسمية، ويعمل به ابتداء من السنة الدراسية 2024-2025، وينسخ ابتداء من نفس التاريخ '
                     'القرار رقم 1227.19 الصادر في 24 من رجب 1440 (31 مارس 2019).')
    assert (began.rule, began.on) == ('stated', d(2024, 9, 1))
    assert in_force('يعمل بهذا القرار ابتداء من السنة الجامعية 2999-3000.').rule == 'condition'       # not begun: its own words
    assert in_force('ينشر هذا القرار بالجريدة الرسمية ويعمل به ابتداء من السنة المالية 2025.').on == d(2025, 1, 1)
    assert in_force('يعمل بهذا المرسوم ابتداء من السنة المالية 1997-1998.').rule == 'condition'       # July to June then


def test_a_part_said_after_the_text_is_not_the_text():
    """Law 57.11's art. 136 repeals the electoral code's provisions on the lists and referendums: the code, a book of
    the library, read «منسوخ» on the day this was first replayed."""
    part = ('تنسخ أحكام القانون رقم 9.97 المتعلق بمدونة الانتخابات، الصادر بتنفيذه الظهير الشريف رقم 1.97.83 بتاريخ 23 من ذي القعدة '
            '1417 (2 أبريل 1997) كما وقع تغييره وتتميمه، المتعلقة باللوائح الانتخابية العامة وبطائق الناخبين وبالاستفتاءات.')
    assert clauses(part) == []
    those = ('تنسخ جميع المقتضيات المخالفة لهذا المرسوم، ولاسيما تلك الواردة في:\n- القرار الصادر في 9 ذي القعدة 1370 (13 أغسطس 1951)؛\n'
             '- والمرسوم رقم 2.74.526 بتاريخ 24 من محرم 1395 (6 فبراير 1975) بتحديد آجال الإخطار.')
    assert clauses(those) == []
    whole = clauses('تنسخ أحكام القانون رقم 26.80 المتعلق بمركز تنمية الطاقات المتجددة الصادر بتنفيذه الظهير الشريف رقم 1.81.346 '
                    'بتاريخ 11 من رجب 1402 (6 ماي 1982).')
    assert [c.kind for c in whole] == ['repeal'] and whole[0].citations[0]['text_number'] == '26-80'
