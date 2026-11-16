"""The blog («قانون بالأرقام», 31 Oct 2026): the first post's figures counted from the issues, the texts they first
published and the words of those texts; its address, its yearly table, and the lead that prints the counted figures."""
import re
from datetime import date

import pytest
from django.utils import timezone

from apps.blog.services import bulletin, posts
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Document, Edition, Issue, Page

pytestmark = pytest.mark.django_db


def issue(number, day, pages, first_page=None, suffix='', head=''):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{number}{suffix}'.ljust(64, '0'),
                                  path=f'BO_{number}{suffix}_ar.pdf', mime='application/pdf', language='ar', bytes=1,
                                  fetched_at=timezone.now(), page_count=pages)
    if head:
        Page.objects.create(document=doc, index=0, kind='scan', text=head)
    return Issue.objects.create(edition=Edition.GENERAL_AR, number=number, suffix=suffix, date=day, document=doc,
                                first_page_number=first_page)


def text(n, kind, published_in, *bodies):
    t = Text.objects.create(akn_uri=f'/akn/ma/act/{kind}/{n}', type=kind, number=n, title_ar=f'نص {n}',
                            first_published_in=published_in)
    v = Version.objects.create(text=t, language='ar', valid_from=published_in.date,
                               consolidation=Consolidation.AS_PUBLISHED)
    for k, body in enumerate(bodies, 1):
        Article.objects.create(version=v, order=k, label=f'المادة {k}', number=str(k), eid=f'art_{k}', body=body)
    # A later consolidation's words are not the year's: only the text as first published counts.
    Version.objects.create(text=t, language='ar', valid_from=date(2030, 1, 1), consolidation=Consolidation.MACHINE)
    return t


def test_a_year_is_counted_issue_by_issue_its_texts_by_kind_and_its_words_as_published():
    wed = issue(3714, date(1984, 1, 4), 23, first_page=1)
    text('1-84-1', 'dahir', wed, 'كلمة كلمة كلمة')
    text('2-84-2', 'decree', wed, 'كلمتان هنا', 'وثلاث كلمات هنا')
    later = issue(3715, date(1984, 1, 11), 47, first_page=25)
    text('10-84', 'order', later, 'قرار')
    text('84-1', 'circular', later, 'دورية')
    issue(3715, date(1984, 1, 13), 300, suffix='bis', head='تقرير حول أنشطة المجلس الأعلى للحسابات برسم سنة 1983')
    issue(3716, date(1984, 1, 18), 12, suffix='bis', head='قرار لم يقطع بعد')
    issue(4341, date(1996, 1, 8), 30, first_page=1)

    f = bulletin.count(1984, 1996, reports_read=[])
    rows = {r[0]: dict(zip(f['year_fields'], r)) for r in f['years']}
    y = rows[1984]
    assert (y['issues'], y['bis'], y['pages'], y['texts']) == (4, 2, 382, 4)
    assert (y['dahir'], y['decree'], y['order'], y['other']) == (1, 1, 1, 1)
    assert y['words'] == 3 + 2 + 3 + 1 + 1
    # The report is the issue whose first page presents one; an uncut issue without a text is not.
    assert (y['report_issues'], y['report_pages']) == (1, 300)
    # The last issue's first page is unread: no printed count rather than a guess.
    assert y['printed'] == 0
    # Wednesdays in 1984, a Monday in 1996; a «bis» is not a day of the week's issue.
    assert f['weekdays'][1984] == [0, 0, 2, 0, 0, 0, 0] and f['weekdays'][1996] == [1, 0, 0, 0, 0, 0, 0]
    assert f['issues'][1984][2] == [3715, 1, 113, 300, 0, 1]
    assert f['thickest'][0] == {'key': '3715-bis', 'date': '1984-01-13', 'pages': 300, 'texts': 0, 'report': True}
    assert f['totals']['issues'] == 5 and f['totals']['pages'] == 412


def test_the_printed_count_is_the_last_first_page_plus_its_pages_when_it_agrees_with_the_files():
    rows = [{'id': k, 'number': 3760 + k, 'suffix': '', 'date': date(1984, 12, 5 + 7 * k), 'first_page_number': fp,
             'document__page_count': pages, 'texts': 1, **dict.fromkeys(bulletin.KINDS, 0)}
            for k, (fp, pages) in enumerate([(1, 1100), (1101, 62)])]
    assert bulletin.tabulate(1984, 1984, rows, set(), {})['years'][0][-1] == 1162
    # A last first page misread by a digit says nothing.
    rows[-1]['first_page_number'] = 2101
    assert bulletin.tabulate(1984, 1984, rows, set(), {})['years'][0][-1] == 0


def test_from_no_1_the_french_editions_own_texts_and_the_copies_stay_apart_and_a_title_alone_is_bare():
    """BH6–BH8 of the posts-from-No.-1 review: a French issue's texts are counted beside the Arabic, never in them; an issue
    whose file is another issue's (a copy) is named, not counted; a text with no words is counted as bare."""
    no1 = issue(1, date(1913, 2, 1), 7, first_page=1)
    text('1913-1', 'dahir', no1, 'نصر مولاي يوسف')
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1913-2', type='dahir', title_ar='ظهير بلا كلمات', first_published_in=no1)
    copy = issue(83, date(1914, 11, 30), 5)
    copy.copy_of = issue(82, date(1914, 11, 23), 5)
    copy.save()
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='fr1'.ljust(64, '0'), path='BO_1_fr.pdf',
                                  mime='application/pdf', language='fr', bytes=1, fetched_at=timezone.now(), page_count=8)
    french = Issue.objects.create(edition=Edition.TRANSLATION_FR, number=1, date=date(1912, 11, 1), document=doc)
    Text.objects.create(akn_uri='/akn/ma/act/arrete/1912-1', type='order', title_ar='قرار مترجم', first_published_in=french)

    f = bulletin.count(1913, 1914, reports_read=[])
    assert f['totals']['issues'] == 2 and f['totals']['texts'] == 2 and f['totals']['pages'] == 12
    assert f['copies'] == {1914: 1} and f['bare'] == {1913: 1}
    assert f['french'] == {1912: [1, 1]}


def test_a_report_issue_a_person_read_counts_though_its_pages_hold_no_text():
    issue(6813, date(2019, 9, 16), 2640, suffix='bis')
    f = bulletin.count(2019, 2019, reports_read=['6813-bis'])
    assert f['thickest'][0]['report'] is True and f['totals']['report_pages'] == 2640


def test_the_blog_lists_its_posts_and_serves_one_with_its_figures_without_a_query(client, django_assert_max_num_queries):
    with django_assert_max_num_queries(0):
        listed = client.get('/api/blog/').json()['posts']
        post = client.get('/api/blog/from-no-1/').json()
        moved = client.get('/api/blog/seventy-years/').json()
        folded = [client.get(f'/api/blog/{s}-in-brief/').json()['slug'] for s in ('countries', 'cities')]
    first = next(p for p in listed if p['slug'] == 'from-no-1')
    assert first['number'] == 1 and first['title']['ar'].startswith('الجريدة الرسمية من العدد 1')
    assert [p['number'] for p in listed] == sorted((p['number'] for p in listed), reverse=True)
    assert 'seventy-years' not in {p['slug'] for p in listed} and moved['slug'] == 'from-no-1'   # the old address leads to it
    assert folded == ['countries', 'cities'] and not any(p['slug'].endswith('-in-brief') for p in listed)
    assert post['span'] == [1913, 2025] and len(post['figures']['years']) == 113
    assert post['figures']['totals']['issues'] == sum(len(v) for v in post['figures']['issues'].values())


def test_an_unknown_post_is_named_in_the_one_error_shape(client):
    for path in ('/api/blog/nothing/', '/api/blog/nothing/years.csv'):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json() == {'errors': [{'field': 'slug', 'code': 'not_found'}]}


def test_the_yearly_table_downloads_as_a_csv_with_the_figures_columns(client):
    response = client.get('/api/blog/from-no-1/years.csv')
    lines = response.content.decode().splitlines()
    assert response['Content-Type'].startswith('text/csv')
    assert lines[0].startswith('year,issues,bis,pages,texts,words') and lines[1].startswith('1913,') and len(lines) == 114


def test_the_lead_prints_the_figures_counted():
    """The lead is written by a person; its figures must be the counted ones, in both languages."""
    totals, lead = posts.figures('from-no-1')['totals'], posts.meta('from-no-1')['lead']
    expected = {totals['issues'], totals['pages']}
    for lang, sep in (('ar', '.'), ('fr', ' ')):
        printed = {int(n.replace(sep, '').replace(' ', '')) for n in re.findall(rf'\d{{1,3}}(?:[{sep} ]\d{{3}})+', lead[lang])}
        assert printed == expected, lang


def constitution(uri, year, *articles):
    t = Text.objects.create(akn_uri=uri, type='constitution', title_ar=f'دستور {year}', signed_on=date(year, 1, 1))
    v = Version.objects.create(text=t, language='ar', valid_from=date(year, 1, 2), consolidation=Consolidation.ADALA)
    for k, (eid, number, title, body) in enumerate(articles, 1):
        Article.objects.create(version=v, order=k, label=number, number=number, eid=eid, heading_path=[title] if title else [],
                               body=body)
    # A later consolidation is not the constitution as issued.
    later = Version.objects.create(text=t, language='ar', valid_from=date(year + 5, 1, 1), consolidation=Consolidation.MACHINE)
    Article.objects.create(version=later, order=1, label='1', number='1', eid='art_1', body='نص معدل طويل جدا جدا')
    return t


def test_the_constitutions_are_counted_as_issued_title_by_title_with_what_became_of_each_article():
    from apps.blog.services import constitutions as six
    general, monarchy = 'الباب الأول: أحكام عامة', 'الباب الثاني: الملكية'
    constitution('/akn/ma/act/dahir/constitution-1962', 1962, ('preamble', 'preamble', '', 'تصدير قصير'),
                 ('art_1', '1', general, 'المغرب مملكة'), ('art_2', '2', monarchy, 'يمارس الملك حق العفو'))
    constitution('/akn/ma/act/dahir/1-70-177', 1970, ('art_1', '1', general, 'المغرب مملكة'),
                 ('art_2', '2', monarchy, 'وللملك قائمة مدنية والملك يعين'))
    meta = {'themes': [{'key': 'general', 'match': 'أحكام عامة'}, {'key': 'monarchy', 'match': 'الملكية'}],
            'terms': [{'key': 'king', 'forms': ['الملك']}]}
    out = six.count(meta)['constitutions']
    assert [c['year'] for c in out] == [1962, 1970]
    first, second = out
    assert (first['articles'], first['words'], first['preamble']) == (2, 6, 2)
    assert [(t['theme'], t['articles']) for t in first['titles']] == [('general', 1), ('monarchy', 1)]
    # The first has nothing before it; in 1970 art. 1 kept its words and art. 2 changed (the corpus's lineage).
    assert [s[2] for s in first['squares']] == [0, 0] and [s[2] for s in second['squares']] == [1, 2]
    # «وللملك» and «الملك» are the same word.
    assert (first['terms']['king'], second['terms']['king']) == (1, 2)
    assert second['published'] == '1970-08-01' and second['path'].startswith('/ma/')
    assert second['quotes'] == [['1', 'المغرب مملكة']]


def test_a_word_counts_in_the_texts_that_carry_it_as_first_published_and_its_first_text_is_named():
    from apps.blog.services import words
    old = issue(2258, date(1956, 2, 3), 10, first_page=1)
    text('2-56-1', 'decree', old, 'الأجر الأدنى مائة فرنك في اليوم')
    new = issue(4564, date(1998, 2, 26), 20, first_page=700)
    t = text('2-97-1024', 'decree', new, 'خدمات الأنترنت', 'ولوج الإنترنت للعموم')
    t.first_published_page = 709
    t.save()
    # A word a later consolidation brought is not the text's word in 1956 (text() adds a machine version).
    later = Version.objects.get(text__number='2-56-1', consolidation=Consolidation.MACHINE)
    Article.objects.create(version=later, order=1, label='1', number='1', eid='art_1', body='الإنترنت')
    meta = {'span': [1956, 1998], 'groups': [{'words': [{'key': 'internet', 'forms': ['الأنترنت', 'الإنترنت']},
                                                         {'key': 'franc', 'forms': ['فرنك']}]}]}
    f = words.count(meta)
    internet, franc = f['words']
    assert len(f['texts']) == 43 and f['texts'][0] == 1 and f['texts'][-1] == 1
    assert internet['years'][0] == 0 and internet['years'][-1] == 1 and franc['years'][0] == 1
    assert internet['first']['date'] == '1998-02-26' and internet['first']['issue'] == '4564' and internet['first']['page'] == 709
    assert internet['first']['path'].endswith('/art_1')


def test_a_word_is_found_folded_counted_from_its_day_and_never_in_a_misread_article():
    """31 Oct 2026: «الامازيغية» as printed in 1983 is «الأمازيغية»; «درهم» before 1959 is a name; a reading the page
    contradicts never counts."""
    from apps.blog.services import words
    text('2-82-472', 'decret', issue(3666, date(1983, 2, 2), 10), 'الدارجة المغربية او الامازيغية او الريفية')
    text('1956-1', 'texte', issue(2272, date(1956, 5, 11), 10), 'بودرهم')
    text('1-59-363', 'dahir', issue(2452, date(1959, 10, 23), 10), 'يكون الدرهم هو الوحدة النقدية')
    text('75-03', 'loi', issue(5282, date(2005, 1, 13), 10), 'الوزارة المكلفة بالحكامة')
    text('2-05-1017', 'decret', issue(5338, date(2005, 7, 28), 10), 'تقوية الحكـامة في ميدان التدبير المحلي')
    meta = {'span': [1956, 2005], 'groups': [{'words': [
        {'key': 'amazigh', 'forms': ['الأمازيغية']},
        {'key': 'dirham', 'forms': ['درهم'], 'since': date(1959, 10, 23)},
        {'key': 'governance', 'forms': ['الحكامة'], 'misread': [{'text': '/akn/ma/act/loi/75-03', 'eid': 'art_1'}]}]}]}
    f = {w['key']: w for w in words.count(meta)['words']}
    assert f['amazigh']['first']['date'] == '1983-02-02' and sum(f['amazigh']['years']) == 1
    assert f['dirham']['first']['date'] == '1959-10-23' and sum(f['dirham']['years']) == 1
    assert f['governance']['first']['date'] == '2005-07-28' and sum(f['governance']['years']) == 1


def test_a_words_stops_name_their_article_issue_and_page_and_a_first_mention_must_hold_the_word():
    from apps.blog.services import words
    t = text('1-01-299', 'dahir', issue(4948, date(2001, 11, 1), 10), 'يحدث المعهد الملكي للثقافة الأمازيغية')
    t.first_published_page = 3677
    t.save()
    adala = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-11-91', type='constitution', title_ar='الدستور')
    v = Version.objects.create(text=adala, language='ar', valid_from=date(2011, 7, 29), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=5, label='الفصل 5', number='5', eid='art_5', body='تعد الأمازيغية أيضا لغة رسمية')
    stops = [{'date': date(2001, 11, 1), 'kind': 'subject', 'text': '/akn/ma/act/dahir/1-01-299', 'art': 1, 'ar': 'المعهد', 'fr': 'IRCAM'},
             {'date': date(2011, 7, 30), 'kind': 'step', 'text': '/akn/ma/act/dahir/1-11-91', 'art': 5, 'issue': '5964-bis',
              'page': 3600, 'ar': 'الدستور', 'fr': 'Constitution'},
             {'date': date(2000, 5, 25), 'kind': 'step', 'issue': '4798', 'page': 1184, 'title': 'قانون رقم 05.00',
              'ar': 'المدرسة', 'fr': 'école'}]
    word = {'key': 'amazigh', 'forms': ['الأمازيغية'], 'stops': stops}
    out = words.resolve_stops([word], {'amazigh': [words.fold('الأمازيغية')]})['amazigh']
    assert [s['date'] for s in out] == ['2000-05-25', '2001-11-01', '2011-07-30']
    assert out[0]['path'] == '/bo/general_ar/4798' and out[0]['title'] == 'قانون رقم 05.00'
    assert out[1]['path'].endswith('/1-01-299/art_1') and (out[1]['issue'], out[1]['page']) == ('4948', 3677)
    assert out[2]['path'].endswith('/art_5') and (out[2]['issue'], out[2]['page']) == ('5964-bis', 3600)
    # A first mention whose article does not hold the word is refused, and so is a day that is not its issue's.
    with pytest.raises(ValueError, match='not in'):
        words.resolve_stops([{**word, 'stops': [{**stops[0], 'kind': 'first', 'text': '/akn/ma/act/dahir/1-11-91', 'art': 5,
                                                 'issue': '5964-bis', 'page': 3600, 'forms': []}]}], {'amazigh': ['الحكامة']})
    with pytest.raises(ValueError, match='its issue is of'):
        words.resolve_stops([{**word, 'stops': [{**stops[0], 'date': date(2001, 11, 2)}]}], {'amazigh': [words.fold('الأمازيغية')]})


def test_who_writes_counts_each_text_by_its_author_ministry_subject_and_kind():
    from apps.blog.services import writers
    meta = {'span': [1965, 2011],
            'authors': [{'key': 'king', 'types': ['dahir']}, {'key': 'ministers', 'types': ['order']}, {'key': 'others', 'types': []}],
            'ministries': [{'key': 'education', 'words': ['التعليم العالي']}, {'key': 'finance', 'words': ['المالية']}],
            'subjects': [{'key': 'equivalence', 'words': ['المعادلات']}, {'key': 'delegation', 'words': ['تفويض الإمضاء']}],
            'laws': [{'key': 'agreement', 'words': ['يوافق بموجبه']}]}
    rows = [(1965, 'dahir', '', 'ظهير'), (1965, 'decree_law', '', 'مرسوم ملكي بمثابة قانون'),
            (2011, 'order', 'وزير المالية ووزير التعليم العالي', 'قرار مشترك بتفويض الإمضاء'),
            (2011, 'order', 'وزير التعليم العالي', 'قرار بتحديد بعض المعادلات'),
            (2011, 'law', '', 'قانون يوافق بموجبه على اتفاق'), (2011, 'law', '', 'قانون يتعلق بالصحافة')]
    f = writers.tabulate(meta, rows)
    assert f['authors']['king'][0] == 1 and f['authors']['ministers'][-1] == 2 and f['authors']['others'][0] == 1
    # A joint order belongs to the first minister its authority names.
    assert f['ministries'] == {'education': 1, 'finance': 1}
    assert f['decades'] == [1960, 1970, 1980, 1990, 2000, 2010]
    assert f['subjects']['equivalence'][-1] == 1 and f['subjects']['delegation'][-1] == 1
    assert f['laws']['agreement'][-1] == 1 and f['laws']['other'][-1] == 1
    assert f['decree_laws'][0] == 1 and sum(f['decree_laws']) == 1


def test_the_months_count_issues_pages_texts_and_kinds_and_read_the_masthead_hijri_month():
    from apps.blog.services import months
    assert months.hijri_month('فاتح رمضان 1447') == 8
    assert months.hijri_month('12 جمادى الاولى 1375') == 4 and months.hijri_month('3 ربيع الثاني 1445') == 3
    assert months.hijri_month('28 ذي الحجة 1443') == 11 and months.hijri_month('') is None
    rows = [(date(1996, 12, 30), '', '18 شعبان 1417', 40, 10, 1, 2, 5),
            (date(1996, 12, 31), 'bis', '19 شعبان 1417', 300, 1, 1, 0, 0),
            (date(1996, 3, 4), '', '14 شوال 1416', 20, 4, 0, 1, 3)]
    f = months.tabulate({'span': [1996, 1996], 'hijri_since': 1996}, rows)
    assert f['months'][0][11] == [2, 1, 340, 11] and f['months'][0][2] == [1, 0, 20, 4]
    assert f['kinds']['laws'][11] == 2 and f['kinds']['orders'][2] == 3
    # A «bis» issue is not a regular one: the Hijri months count regular issues only.
    assert f['hijri'][7] == [1, 10, 40] and f['hijri'][9] == [1, 4, 20]


def test_each_wage_step_is_tied_to_its_decree_issue_and_page():
    from apps.blog.services import wages
    old = issue(2258, date(1956, 2, 3), 30, first_page=170)
    t = Text.objects.create(akn_uri='/akn/ma/act/texte/1956-02-03/bo2258-2', type='other', title_ar='مرسوم وزاري يزاد بموجبه في الاجرة الدنيا',
                            first_published_in=old, first_published_page=174)
    new = issue(7469, date(2025, 12, 29), 40, first_page=10000)
    text('2-25-983', 'decree', new, 'ابتداء من فاتح يناير 2026، يحدد في سبعة عشر درهما')
    meta = {'steps': [{'decree': '', 'issue': '2258'}, {'decree': '2-25-983'}]}
    d = wages.count(meta)['decrees']
    assert d['2258']['page'] == 174 and d['2258']['issue'] == '2258' and t.akn_uri.endswith(d['2258']['path'].split('/')[-1])
    assert d['2-25-983']['issue'] == '7469' and d['2-25-983']['published'] == '2025-12-29'


def test_each_holiday_list_is_tied_to_its_text_issue_and_page():
    from apps.blog.services import holidays
    one = issue(3388, date(1977, 10, 5), 20, first_page=2780)
    text('2-77-249', 'decree', one, 'ان يوم فاتح مايو (عيد الشغل)')
    meta = {'private': [{'text': '2-77-249'}], 'administration': [{'text': '1-57-393'}], 'once': {'text': '178-65'}}
    texts = holidays.count(meta)['texts']
    assert list(texts) == ['2-77-249'] and texts['2-77-249']['issue'] == '3388' and texts['2-77-249']['published'] == '1977-10-05'


def test_no_post_meta_loses_words_to_an_unquoted_comma():
    """In a YAML {…} mapping an unquoted comma ends the value: «fr: 11 janvier, Manifeste…» became «11 janvier» and an
    empty key (31 Oct 2026). Every value of every post's meta is whole."""
    def empty_keys(x):
        if isinstance(x, dict):
            return [k for k, v in x.items() if v is None and k != 'date'] + [e for v in x.values() for e in empty_keys(v)]
        return [e for v in x for e in empty_keys(v)] if isinstance(x, list) else []
    for slug in posts.slugs():
        assert empty_keys(posts.meta(slug)) == [], slug


def test_waits_measure_each_text_from_its_signature_and_leave_out_what_cannot_be_measured():
    from apps.blog.services import waits
    rows = [('law', '25-85', date(1984, 12, 17), date(1993, 7, 21), 4212, '', 1, '/akn/ma/act/loi/25-85',
             'قانون رقم 25.85 يتعلق بالموافقة من حيث المبدأ على تصديق الاتفاقية'),
            ('law', '65-00', date(2002, 10, 3), date(2002, 10, 3), 5058, '', 3449, '/akn/ma/act/loi/65-00', 'قانون رقم 65.00 بمثابة مدونة'),
            ('order', '1-20', date(2020, 1, 1), date(2020, 2, 14), 6860, '', 1, '/akn/ma/act/arrete/1-20', 'قرار'),
            ('decree', '2-20-1', date(2020, 3, 1), date(2020, 1, 1), 6850, '', 1, '/akn/ma/act/decret/2-20-1', 'مرسوم'),
            ('law', '1-76-583', date(1976, 9, 30), date(1977, 10, 10), 3388, '', 1, '/akn/ma/act/loi/x', 'قانون (استدراك)'),
            ('dahir', '1-75-439', date(1977, 2, 16), date(1981, 12, 16), 3606, '', 1, '/akn/ma/act/dahir/1-75-439', 'ظهير بنشر الاتفاقية الجمركية')]
    f = waits.tabulate({'span': [1956, 2025]}, rows)
    assert f['left_out'] == {'no_date': 0, 'after': 1, 'erratum': 1} and f['kept'] == 4
    assert f['overall']['law_agreement'] == 3138 and f['overall']['law'] == 0 and f['overall']['order'] == 44
    assert f['overall']['dahir_agreement'] == 1764 and f['same_day'] == 1
    assert [law[1] for law in f['laws']] == [3138, 0] and f['late'][0]['number'] == '25-85' and f['late'][0]['agreement']
    assert waits.band(7) == 0 and waits.band(8) == 1 and waits.band(366) == 4


def test_a_correction_counts_once_for_its_issue_and_the_issue_it_names_and_is_timed_between_them():
    from apps.blog.services import errata
    old = issue(4628, date(1998, 10, 8), 1)
    names = issue(4286, date(1994, 12, 21), 1)
    issue(2373, date(1958, 4, 18), 1)
    late = issue(7271, date(2024, 2, 5), 2)
    Page.objects.filter(document=late.document).delete()
    # The index and the page carry the same notice: one correction, of a decree, 9,251 days late.
    Page.objects.create(document=late.document, index=0, kind='scan', text=(
        'استدراك خطإ وقع بالجريدة الرسمية عدد 4628 بتاريخ 16 من جمادى الآخرة 1419 (8 أكتوبر 1998) ........ 726\n\n'
        'استدراك خطإ وقع بالجريدة الرسمية عدد 4286 بتاريخ 21 دیسمبر 1994 ........ 727'))
    Page.objects.create(document=late.document, index=1, kind='scan', text=(
        'استدراك خطأ وقع بالجريدة الرسمية عدد 4628 بتاريخ 16 من جمادى الآخرة 1419 (8 أكتوبر 1998)، الصفحة 2877\n\n'
        'مرسوم رقم 2.98.661 بالموافقة على عملية التحديد الإداري\n\nبدلا من : 1924\n\nيقرأ : 1954\n\n'
        # A pension list's row is no notice; nor is a notice naming an issue printed after it.
        'استدراك | تحويل المعاش المدني رقم 21.425 المنشور بالجريدة الرسمية عدد 2876\n\n'
        'استدراك خطإ وقع بالجريدة الرسمية عدد 7300 بتاريخ 2025\n\n'
        # 1958's dotted thousands, and a list of names: the year printed (1985) is not 2373's, so it is not timed.
        'استدراك للجريدة الرسمية عدد 2.373 الصادرة سنة 1985\n\nنتائج مباراة لتوظيف كتاب الضبط\n\nبدلا من : فلان'))
    issue(7300, date(2025, 3, 1), 0)
    f = errata.count({'span': [1956, 2025]})
    assert f['notices'] == 3 and f['timed'] == 2 and f['left_out'] == {'after': 1, 'misread': 1}
    assert f['longest'][1] == {'printed': '2024-02-05', 'printed_issue': '7271', 'corrected': '1998-10-08',
                               'corrected_issue': '4628', 'days': 9251, 'kind': 'decree'}
    assert f['longest'][0]['corrected_issue'] == '4286' and f['longest'][0]['kind'] == 'index'
    decade = f['decades'].index(2020)
    assert f['per_decade']['notices'][decade] == 3 and f['per_decade']['names'][decade] == 1 and f['years'][-2] == 3
    assert f['per_decade']['issues'][f['decades'].index(1990)] == 2 and old.number == 4628 and names.number == 4286
    assert f['band_counts'] == [0, 0, 0, 0, 0, 2] and f['arcs'][0][:4] == ['1994-12-21', '2024-02-05', '4286', '7271']


def test_the_errata_lead_prints_the_corrections_counted_and_each_example_is_one_of_them():
    f, m = posts.figures('errata'), posts.meta('errata')
    for lang, sep in (('ar', '.'), ('fr', ' ')):
        printed = {int(n.replace(sep, '')) for n in re.findall(rf'\d{{1,3}}(?:{sep}\d{{3}})+', m['lead'][lang])}
        assert printed == {f['notices']}, lang
    pairs = {(a[2], a[3]) for a in f['arcs']}
    assert all((e['corrected_issue'], e['printed_issue']) in pairs for e in m['examples'])


def test_agreements_are_sorted_by_what_the_text_does_and_who_the_partner_is():
    from apps.blog.services import agreements
    rows = [
        ('decree', '2-24-806', date(2024, 9, 2), '/akn/ma/act/decret/2-24-806',
         'مرسوم رقم 2.24.806 بالموافقة على اتفاق القرض رقم 9317-MA المبرم بين المملكة المغربية والبنك الدولي للإنشاء والتعمير'),
        # A guarantee for a public body, the lender written with «لل»; the Kuwait Fund is not Kuwait.
        ('decree', '2-10-556', date(2011, 1, 6), '/akn/ma/act/decret/2-10-556',
         'مرسوم رقم 2.10.556 بالموافقة على الاتفاقية المبرمة بين المملكة المغربية والصندوق الكويتي للتنمية الاقتصادية العربية، لضمان قرض الممنوح للمكتب الوطني للكهرباء'),
        ('dahir', '1-99-241', date(2002, 11, 21), '/akn/ma/act/dahir/1-99-241',
         'ظهير شريف رقم 1.99.241 بنشر الاتفاقية بشأن التسوية السلمية للنزاعات الدولية الموقعة بلاهاي في 18 أكتوبر 1907'),
        ('dahir', '1-59-251', date(1960, 2, 5), '/akn/ma/act/dahir/1-59-251',
         'ظهير شريف رقم 1.59.251 في المصادقة على الاتفاق المتعلق بالنقل الجوي الموقع بالرباط بتاريخ 3 أبريل 1958 بين المغرب والبرتغال'),
        ('law', '08-24', date(2025, 5, 1), '/akn/ma/act/loi/08-24',
         'قانون رقم 08.24 يوافق بموجبه على الاتفاق بين حكومة المملكة المغربية وحكومة جمهورية غامبيا بشأن المساعدة المتبادلة'),
        # At home: a petroleum agreement and an aquaculture licence, though their titles say «اتفاق».
        ('order', '1-23', date(2023, 1, 1), '/akn/ma/act/arrete/1-23', 'قرار مشترك بالموافقة على الاتفاق النفطي «HAHA ONSHORE»'),
        ('decree', '2-21-198', date(2021, 4, 1), '/akn/ma/act/decret/2-21-198', 'مرسوم يقضي بالمصادقة على اتفاقية التدبير المفوض لأكاديمية الموضة'),
    ]
    f = agreements.tabulate({'span': [1956, 2025]}, rows)
    assert f['sorted'] == {'money': 2, 'treaty': 2, 'law': 1, 'domestic': 2}
    assert [(m[2], f['kinds'][m[1]]) for m in f['money']] == [('kuwait_fund', 'guarantee'), ('world_bank', 'loan')]
    assert f['borrowers'] == [{'key': 'onee', 'n': 1}] and f['law_regions']['africa'][-1] == 1
    assert f['treaty_regions'] == {'multilateral': [0, 0, 0, 0, 0, 1, 0, 0], 'europe': [0, 1, 0, 0, 0, 0, 0, 0]}
    assert f['oldest'][0]['years'] == 95 and f['last_publication'] == '2002-11-21' and f['names']['kuwait_fund']['short_ar']


def test_the_agreements_lead_prints_the_loans_counted():
    f, m = posts.figures('agreements'), posts.meta('agreements')
    for lang, sep in (('ar', '.'), ('fr', ' ')):
        printed = {int(n.replace(sep, '')) for n in re.findall(rf'\d{{1,3}}(?:{sep}\d{{3}})+', m['lead'][lang])}
        assert printed == {len(f['money'])}, lang
    assert str(sum(f['treaties_per_decade'])) in m['lead']['ar'] and f['last_publication'] < '2026'


def test_countries_are_shares_of_each_period_with_and_without_the_diploma_lists():
    from apps.blog.services import countries
    meta = {'periods': [[1956, 1969], [1970, 1979], [2010, 2019], [2020, 2025]], 'moves': {'floor': 1, 'most': 3}}
    places = [
        {'slug': 'france', 'kind': 'country', 'name_ar': 'فرنسا', 'name_fr': 'France', 'name_en': 'France', 'lat': 46.7, 'lon': 2.5,
         'successor': '', 'region': 'Europe/Western Europe', 'texts': 30, 'spellings': [{'form': 'فرنسا'}],
         'first': {'date': '1956-05-11', 'issue': '2272', 'edition': 'general_ar', 'page': 755, 'form': 'فرنسا', 'title': 'اعلان'}},
        {'slug': 'ukraine', 'kind': 'country', 'name_ar': 'أوكرانيا', 'name_fr': 'Ukraine', 'name_en': 'Ukraine', 'lat': 49.0, 'lon': 31.0,
         'successor': '', 'region': 'Europe', 'texts': 10, 'spellings': [],
         'first': {'date': '2021-01-07', 'issue': '6950', 'edition': 'general_ar', 'page': 1, 'form': 'أوكرانيا', 'title': 'قرار'}},
        {'slug': 'soviet-union', 'kind': 'gone', 'name_ar': 'الاتحاد السوفياتي', 'name_fr': 'URSS', 'name_en': 'Soviet Union', 'lat': 60.0,
         'lon': 90.0, 'successor': 'russia', 'region': '', 'texts': 2, 'spellings': [], 'first': None},
        {'slug': 'tuvalu', 'kind': 'country', 'name_ar': 'توفالو', 'name_fr': 'Tuvalu', 'name_en': 'Tuvalu', 'lat': None, 'lon': None,
         'successor': '', 'region': 'Oceania', 'texts': 0, 'spellings': [], 'first': None},
    ]
    years = [('france', 1960, 20, {'treaty': 20}), ('france', 2021, 10, {'studies': 6, 'other': 4}),
             ('ukraine', 2021, 10, {'studies': 9, 'other': 1}), ('soviet-union', 1960, 2, {'treaty': 2})]
    totals = [(1960, 1000, 22), (1975, 1000, 0), (2015, 1000, 0), (2021, 2000, 20)]
    f = countries.tabulate(meta, places, years, totals)
    by = {s['slug']: s for s in f['states']}
    assert by['france']['s'] == [20.0, 0, 0, 5.0] and by['france']['x'] == [20.0, 0, 0, 2.0]
    assert by['ukraine']['s'] == [0, 0, 0, 5.0] and by['ukraine']['x'] == [0, 0, 0, 0.5]
    assert f['moves'] == {'rose': ['ukraine'], 'fell': ['france']}
    assert f['never'] == [{'ar': 'توفالو', 'fr': 'Tuvalu'}] and by['soviet-union']['gone']
    assert f['baseline'] == [22.0, 0, 0, 10.0] and f['climb']['counts'][0] == 1 and f['climb']['counts'][-1] == 2


def test_a_city_counts_with_its_province_each_text_once():
    from apps.blog.services import cities
    meta = {'periods': [[1956, 1969], [2020, 2025]], 'moves': {'floor': 1, 'most': 3}, 'people_floor': 1}
    city = lambda pk, slug, pop, old=(): {'pk': pk, 'slug': slug, 'kind': 'city', 'name_ar': slug, 'name_fr': slug, 'lat': 1, 'lon': 1,
                                           'population': pop, 'town': '', 'parent': '', 'texts': 0, 'first': None, 'spellings': [], 'old': list(old)}
    cs = [city(1, 'taza', 1000), city(2, 'errachidia', 2000, ['قصر السوق'])]
    provinces = [{'pk': 9, 'town': 'taza', 'population': 10000}]
    rows = [(1, '/a', 1960, 'land', False), (9, '/a', 1960, 'territory', False), (9, '/b', 2021, 'courts', False),
            (2, '/c', 1960, 'other', True), (2, '/d', 2021, 'other', False)]
    f = cities.tabulate(meta, cs, provinces, rows, [(1960, 100, 0), (2021, 200, 0)])
    by = {c['slug']: c for c in f['cities']}
    assert by['taza']['c'] == [1, 1] and by['taza']['pop'] == 10000
    assert by['errachidia']['old'] == {'forms': ['قصر السوق'], 'c': [1, 0]}
    assert f['people'][0] == {'slug': 'errachidia', 'v': 5.0} and f['people'][1] == {'slug': 'taza', 'v': 1.0}


@pytest.mark.parametrize('slug', ['countries', 'cities'])
def test_the_places_leads_print_the_texts_counted(slug):
    f, m = posts.figures(slug), posts.meta(slug)
    for lang, sep in (('ar', '.'), ('fr', ' ')):
        printed = {int(n.replace(sep, '')) for n in re.findall(rf'\d{{1,3}}(?:{re.escape(sep)}\d{{3}})+', m['lead'][lang])}
        assert printed == {f['totals']['texts']}, lang


def test_a_text_citing_a_correction_is_not_a_correction():
    """BO 2629 of 1963: a code's references cite the correction BO 803 printed in 1928; it is not a notice of 1963."""
    from datetime import date
    from apps.blog.services import errata
    page = ('المراجع الظهير الشريف الصادر في 25 يونيو 1927 (الجريدة الرسمية عدد 766) وكذا الاستدراك المنشور بالجريدة '
            'الرسمية عدد 803 الصادرة في 13 مارس 1928 الصحيفة 743.\n\nاستدراك خطإ وقع بالجريدة الرسمية عدد 2600\n'
            'مرسوم رقم 2.62.100 … عوض … يقرأ …')
    found = errata.notices([(date(1963, 3, 15), 2629, '', page)])
    assert list(found) == [((2629, False), (2600, False))]


def test_the_old_bulletins_loan_is_salaf_and_its_credit_at_home_stays_at_home():
    """BH5: «سلف» is a loan before 1956; the Protectorate's credit funds sort as domestic or other, never as money abroad."""
    from apps.blog.services import agreements
    assert agreements.LOAN.search(agreements.fold('ظهير شريف في الاذن بعقد سلف'))
    assert not agreements.LOAN.search(agreements.fold('المذهب السلفي')) and not agreements.LOAN.search('دفع سلفا')
    funds = agreements.sort('order', 'قرار وزيري في تخصيص سلف للصندوق المركزي للسلف الفلاحي بالناحية الجنوبية بالايالة الشريفة')
    assert funds['what'] in ('domestic', 'other')


def test_the_old_bulletins_corrections_are_found_by_their_old_heading():
    """BH5 of the posts-from-No.-1 review: before 1956 a correction is «اصلاح غلط», and a page may be named before the issue."""
    from datetime import date
    from apps.blog.services import errata
    page_1946 = 'اصلاح غلط واقع في الجريدة الرسمية العربية عدد 1744 بصحيفة عدد 223 في ظهير شريف مورخ في 9 يبراير 1946'
    page_1952 = 'استدراك لاصلاح غلط فـي الصحيفة 6542 مـن عدد الجريدة الرسمية العربية رقم 2089 الصادرة يوم 7 نونبر 1952'
    page_1914 = 'إصلاح غلط وقع في الجريدة الرسمية عدد ٨٢ الصادرة في ٢٣ نونبر ١٩١٤ في القرار الوزيري'
    found = errata.notices([(date(1946, 3, 1), 1750, '', page_1946), (date(1952, 12, 1), 2093, '', page_1952),
                            (date(1914, 12, 7), 84, '', page_1914)])
    assert set(found) == {((1750, False), (1744, False)), ((2093, False), (2089, False)), ((84, False), (82, False))}
    assert found[((84, False), (82, False))]['years'] == {1914}


def test_a_country_named_before_the_posts_span_counts_from_its_first_year_in_it():
    """1 Nov 2026: with the Bulletin read from 1913, the post's climb (from 1956) had lost every state named earlier."""
    from apps.blog.services import countries
    meta = {'periods': [[1956, 1969], [2020, 2025]], 'moves': {'floor': 1, 'most': 3}}
    first = {'date': '1928-05-04', 'issue': '811', 'edition': 'general_ar', 'page': 3, 'form': 'فرنسا', 'title': 'ظهير'}
    places = [{'slug': 'france', 'kind': 'country', 'name_ar': 'فرنسا', 'name_fr': 'France', 'name_en': 'France',
               'lat': 46.7, 'lon': 2.5, 'successor': '', 'region': 'europe', 'texts': 3, 'first': first, 'spellings': []}]
    years = [('france', 1928, 1, {'other': 1}), ('france', 1957, 2, {'other': 2}), ('france', 2021, 1, {'other': 1})]
    out = countries.tabulate(meta, places, years, [(1957, 10, 2), (2021, 10, 1)])
    (state,) = out['states']
    assert state['first'] == {'year': 1957, 'named_before': 1928}
    assert out['climb']['counts'][1957 - 1956] == 1


def test_each_clock_text_is_tied_to_its_issue_its_printed_page_and_its_address_and_ramadan_comes_from_the_mastheads():
    """«من غرينيتش إلى غرينيتش»: a text the site has cut opens its address; one it has not, its printed page; a «bis» issue
    without printed numbers is found by its page's index; Ramadan's first day is the one most issues of the year date."""
    from apps.blog.services import clock
    cut = issue(7521, date(2026, 6, 29), 30, first_page=3740)
    Page.objects.create(document=cut.document, index=28, kind='scan', printed_number=3768, text='مرسوم رقم 2.26.530')
    text('2-26-530', 'decree', cut, 'الرجوع إلى الساعة القانونية')
    bis = issue(6720, date(2018, 10, 27), 3, suffix='bis')
    Page.objects.create(document=bis.document, index=1, kind='scan', text='مرسوم رقم 2.18.855')
    old = issue(2868, date(1967, 10, 18), 40, first_page=2283)
    Page.objects.create(document=old.document, index=1, kind='scan', printed_number=2284, text='مرسوم ملكي رقم 726.67')
    for n, day, hijri in ((7486, date(2026, 2, 23), '5 رمضان 1447'), (7487, date(2026, 2, 26), '8 رمضان 1447'),
                          (7488, date(2026, 3, 23), '4 شوال 1447'), (7489, date(2026, 3, 9), '19 رمضان 1447')):
        Issue.objects.filter(pk=issue(n, day, 1).pk).update(hijri_date=hijri)
    meta = {'texts': [
        {'key': 'end', 'edition': 'general_ar', 'issue': 7521, 'page': 3768, 'akn': '/akn/ma/act/decree/2-26-530'},
        {'key': 'kept', 'edition': 'general_ar', 'issue': 6720, 'bis': True, 'page': 8880, 'index': 1},
        {'key': 'back', 'edition': 'general_ar', 'issue': 2868, 'page': 2284, 'akn': '/akn/ma/act/decret/726-67'},
    ]}
    f = clock.count(meta)
    end, kept, back = f['texts']['end'], f['texts']['kept'], f['texts']['back']
    assert end['path'] == '/ma/decree/2-26-530' and end['published'] == '2026-06-29' and end['viewer'] == f'/pages/{cut.document_id}/28'
    assert kept['issue'] == '6720 bis' and kept['viewer'] == f'/pages/{bis.document_id}/1' and kept['path'] is None
    assert back['path'] is None and back['viewer'] == f'/pages/{old.document_id}/1'   # not cut: its printed page
    assert f['hijri']['ramadan']['2026'] == '2026-02-19' and f['hijri']['shawwal']['2026'] == '2026-03-20'


def test_the_clock_posts_moves_run_in_time_each_named_by_a_text_it_reads_with_its_words_in_both_languages():
    meta = posts.meta('clock')
    keys = {t['key'] for t in meta['texts']}
    ats = [m['at'] for m in meta['moves']]
    assert ats == sorted(ats) and len(set(ats)) == len(ats)
    assert {m['text'] for m in meta['moves']} <= keys and {u['set'] for u in meta['undone']} | {u['by'] for u in meta['undone']} <= keys
    assert set(meta['words']) == keys and all(w['ar'] and w['fr'] for w in meta['words'].values())
    assert set(posts.figures('clock')['texts']) == keys and all(v['viewer'] for v in posts.figures('clock')['texts'].values())


def test_the_marquise_orders_and_the_texts_it_quotes_are_tied_to_their_pages_and_the_wage_comes_from_the_sixth_post():
    """«ماركيز، قرارا بعد قرار»: every order and every text the post quotes opens its printed page; the minimum wage is the
    sixth post's checked series (a step whose decree names no day starts on its issue's day); the orders are sorted by
    the verb of their titles."""
    from apps.blog.services import marquise
    meta = posts.meta('marquise')
    refs = marquise._refs(meta)
    assert len(refs) == len(meta['prices']) + 5 + len(meta['palestine']['changed'])
    assert {r['key'] for r in refs} == set(posts.figures('marquise')['texts'])
    assert all(v['viewer'] for v in posts.figures('marquise')['texts'].values())
    w = marquise.wage()
    assert w[0] == {'from': '1960-01-15', 'hourly': 0.808, 'decree': '2-59-1986', 'issue': '2464', 'path': '/ma/decret/2-59-1986'}
    assert [x['from'] for x in w] == sorted(x['from'] for x in w) and w[-1]['hourly'] == 17.92
    orders = posts.figures('marquise')['orders']
    assert all(v == 'set' for d, v in orders if d < '2013-03') and all(v == 'approve' for d, v in orders if d >= '2013-03')


def test_an_order_on_tobacco_prices_is_sorted_by_the_verb_of_its_title_and_tangier_is_left_out():
    from apps.blog.services import marquise
    day = issue(6138, date(2013, 3, 28), 4, first_page=2700)
    for n, title in (('771-13', 'قرار للوزير المنتدب يتعلق بالمصادقة على أسعار بيع التبغ المصنع للعموم'),
                     ('587-10', 'قرار لوزير الاقتصاد والمالية بتحديد الأسعار التي يباع بها للعموم التبغ المصنع'),
                     ('1-58', 'قرار يحدد أثمان بيع التبغ والسجائر بعمالة طنجة')):
        Text.objects.create(akn_uri=f'/akn/ma/act/arrete/{n}', type='order', number=n, title_ar=title, first_published_in=day)
    meta = {'prices': [], 'renamed': {'issue': 1, 'page': 1}, 'approve': {'issue': 1, 'page': 1}, 'delegate': {'issue': 1, 'page': 1},
            'palestine': {'dahir': {'issue': 1, 'page': 1}, 'applied': {'issue': 1, 'page': 1}, 'changed': []}}
    assert sorted(marquise.count(meta)['orders']) == [['2013-03-28', 'approve'], ['2013-03-28', 'set']]


def test_the_bread_and_gasoil_orders_are_tied_to_their_pages_and_their_days_hold():
    """«الخبز والغازوال»: every order the post names (the basket's fifteen, the 1975 loaf, the 23 gasoil prices, the last
    one, the two that took the price away) opens its printed page; the basket's days are the orders' own (29 May and 7 June
    1981, each order's last article); the gasoil steps run in order and the last printed price closes them."""
    from apps.blog.services import staples
    meta = posts.meta('bread-gasoil')
    refs = staples._refs(meta)
    assert len(refs) == 5 * 3 + 1 + len(meta['gasoil']) + 1 + len(meta['away']) == 42
    assert {r['key'] for r in refs} == set(posts.figures('bread-gasoil')['texts'])
    assert all(v['viewer'] for v in posts.figures('bread-gasoil')['texts'].values())
    assert [str(i['from']) for i in meta['issues']] == ['1980-09-05', '1981-05-29', '1981-06-07']
    assert all(len(b['values']) == len(b['orders']) == 3 for b in meta['basket'])
    froms = [str(g['from']) for g in meta['gasoil']]
    assert froms == sorted(froms) and froms[-1] < str(meta['last']['from']) == str(meta['away'][1]['from'])
    assert posts.figures('bread-gasoil')['wage'][0]['from'] == '1960-01-15'


def test_the_ages_and_the_texts_that_moved_them_are_tied_to_their_pages():
    """«حياتك بأعمار القانون»: every age, every step of an age that moved, and the two quotes open their printed page; an
    age an amending law wrote opens the article of the code it amended; the lead's counts are the meta's."""
    from apps.blog.services import ages
    meta = posts.meta('ages')
    refs = ages._refs(meta)
    real = [a for a in meta['ages'] if not a.get('echo')]
    assert len(refs) == len(meta['ages']) + sum(len(m['steps']) for m in meta['moves']) + 2
    assert {r['key'] for r in refs} == set(posts.figures('ages')['texts'])
    assert all(v['viewer'] for v in posts.figures('ages')['texts'].values())
    assert len(real) == 35 and len({a['law'] for a in real}) == 14 and len(meta['moves']) == 7
    assert sum(a['age'] < 26 for a in real) == 28 and [a['age'] for a in real if 26 <= a['age'] <= 54] == [40]
    articles = posts.figures('ages')['articles']
    assert articles['a-prison14'] == '/ma/loi/22-01/art_473' and articles['a-majority'] == '/ma/loi/70-03/art_209'
    assert all(a['side'] in ('start', 'end') and (a.get('to') is None or a['from'] < a['to']) for a in meta['ages'])


def test_the_order_of_1967_its_family_and_the_dahir_of_1913_are_tied_to_their_pages():
    """«الفصل 28»: the order, its articles named, the texts that delegated and changed it, the 1913 dahir's three pages and
    the public drunkenness decree each open their printed page; the order's articles open their address; the fines are
    the eighteen the order sets, article 28 at 300 to 1.500 dirhams."""
    from apps.blog.services import drinks
    meta = posts.meta('article-28')
    refs = drinks._refs(meta)
    assert {r['key'] for r in refs} == set(posts.figures('article-28')['texts'])
    assert all(v['viewer'] and v['path'] for v in posts.figures('article-28')['texts'].values())
    assert {'f-56', 'f-57', 'f-58', 'art28', 'drunk', 'c-delegation'} <= {r['key'] for r in refs}
    assert len(meta['fines']) == 18 and [f for f in meta['fines'] if f['art'] == 28] == [{'art': 28, 'lo': 300, 'hi': 1500, 'prison': [1, 6], 'or': True}]
    assert posts.figures('article-28')['articles']['28'] == '/ma/decision/1967/3-177-66/art_28'


def test_the_six_constitutions_the_law_and_the_organic_laws_of_2011_are_tied_to_their_pages():
    """«حق الإضراب مضمون»: each constitution's article, article 86's deadline, organic law 97.15, the Constitutional Court's
    decision, the 22 organic laws of the 2011 Constitution and the order naming the 2016 election day open their printed
    page and their text; the law's articles named open their address."""
    from apps.blog.services import strike
    meta = posts.meta('strike')
    refs = strike._refs(meta)
    assert {r['key'] for r in refs} == set(posts.figures('strike')['texts'])
    assert all(v['viewer'] and v['path'] for v in posts.figures('strike')['texts'].values())
    assert [c['year'] for c in meta['constitutions']] == [1962, 1970, 1972, 1992, 1996, 2011]
    assert len(meta['organic']) == 22 and sum(o['date'] > meta['election']['date'] for o in meta['organic']) == 4
    assert posts.figures('strike')['articles']['21'] == '/ma/loi-organique/97-15/art_21'


def test_the_machines_the_networks_and_the_mediator_are_tied_to_their_pages():
    """«القانون يعرف البرقية، ولا يعرف واتساب»: each machine's quoted text, each network's first page, the two clippings,
    the Mediator's two reports, the CESE's chart and the naming quotes open their printed page; the articles quoted open
    their address; no text of law names a network once the five defects the meta lists are set aside."""
    from apps.blog.services import absent
    meta = posts.meta('whatsapp')
    figures = posts.figures('whatsapp')
    refs = absent._refs(meta)
    assert {r['key'] for r in refs} == set(figures['texts'])
    assert all(v['viewer'] for v in figures['texts'].values())
    assert [m['key'] for m in meta['machines']] == ['telegram', 'typewriter', 'fax', 'telex']
    assert sum(1 for a in meta['apps'] if a.get('pct')) == 10
    assert all(a['texts'] == 0 for a in figures['apps']) and figures['checks'] == []
    assert len(meta['not_law']) == 5
    assert figures['articles']['m-fax'] == '/ma/decret/2-22-431/art_29'


def test_the_death_penalty_articles_steps_and_reports_are_tied_to_their_pages():
    """«الإعدام في القانون المغربي»: each article of the penal code that names the death penalty opens its page in the
    1963 printing (or law 03.03's), the other texts, every step of the procedure and the CNDH's reports open theirs; the
    code is drawn whole and its marked articles are the meta's."""
    from apps.blog.services import death
    meta = posts.meta('death-penalty')
    figures = posts.figures('death-penalty')
    refs = death._refs(meta)
    assert {r['key'] for r in refs} == set(figures['texts'])
    assert all(v['viewer'] for v in figures['texts'].values())
    assert sum(a['kind'] == 'death' for a in meta['articles']) == 30 and figures['checks'] == []
    assert len(figures['cells']) == 732
    assert figures['articles']['s-press'] == '/ma/loi/22-01/art_606'


def test_the_laws_by_who_made_them_and_the_constitutions_words_are_tied():
    """«على كل قانون يصوّت عليه البرلمان»: the constitutions' transitional articles and the two decrees of June 1965 open
    their printed page; the hands are read from titles (a royal decree «بمثابة قانون» before a voted law); the ratio is
    the title's."""
    from apps.blog.services import parliament
    meta = posts.meta('parliament')
    figures = posts.figures('parliament')
    assert {r['key'] for r in parliament._refs(meta)} == set(figures['texts'])
    assert all(v['viewer'] for v in figures['texts'].values())
    hands = [(h['key'], parliament.re.compile(h['re'])) for h in meta['hands']]
    assert parliament._hand('مرسوم ملكى رقم 267.66 بمثابة قانون يتعلق بمنح بعض الفلاحين', hands) == 'rdl'
    assert parliament._hand('ظهير شريف رقم 1.77.278 بمثابة القانون التنظيمي للمحكمة العليا', hands) == 'dfl'
    assert parliament._hand('ظهير شريف رقم 1.16.12 صادر في 6 جمادى الأولى بتنفيذ القانون رقم 31.13', hands) == 'voted'
    assert figures['ratio'] == {'decrees': 14, 'orders': 52, 'share': 84}


def test_the_speeds_are_tied_to_their_pages_and_the_orders_read():
    """«السرعة في الجريدة الرسمية»: each era opens its printed page (the 1924 order in the French edition), the 1914 rule
    and the 2010 decree's articles theirs; an order's speed is read in digits or in words."""
    from apps.blog.services import speed
    meta = posts.meta('speed')
    figures = posts.figures('speed')
    assert {r['key'] for r in speed._refs(meta)} == set(figures['texts'])
    assert all(v['viewer'] for v in figures['texts'].values())
    assert speed.kmh('تحدد السرعة القصوى للسيارات في ستين كيلومترا في الساعة (هكذا 60) بالطريق') == 60
    assert speed.kmh('تحدد السرعة القصوى للسيارات بمائة وعشرين كيلومترا في الساعة على الطريق رقم 36') == 120
    assert speed.kmh('تحدد بأربعين (40) كيلومترا في الساعة السرعة القصوى') == 40
    assert speed.kmh('تقدر أقصى حد سرعة السيارات بستين كيلومترا في الساعة (60 كلم)') == 60


def test_a_deadline_is_a_number_after_a_word_that_makes_it_a_limit():
    """«15 يوما: الأجل المفضل»: numbers in digits, in words (with or without the article), as duals; ages and exam
    lengths, with no limit word before them, are not deadlines."""
    from apps.blog.services import deadlines
    meta = posts.meta('deadlines')
    number, dual = deadlines._patterns(meta['limit_words'])
    found = lambda s: [(u, n) for u, n, _, _ in deadlines.deadlines(s, number, dual)]
    assert found('داخل أجل خمسة عشر يوما من تاريخ الخطاب') == [('d', 15)]
    assert found('خلال الخمسة عشر يوما الموالية') == [('d', 15)]
    assert found('خلال الإثني عشر شهرا') == [('m', 12)]
    assert found('في أجل لا يتجاوز ستة أشهر من تاريخ تقديم الطلب') == [('m', 6)]
    assert found('خلال أجل لا يتعدى شهرين') == [('m', 2)]
    assert found('داخل أجل ثلاثة (3) أيام') == [('d', 3)]
    assert found('ألا يتجاوز سنه 45 سنة') == []
    assert found('مدتها ثلاث ساعات') == []
    assert posts.figures('deadlines')['deadlines'][0]['n'] == 15


def test_an_expropriation_is_read_by_what_its_title_says_it_is_for():
    """«نزع الملكية»: the purpose is read after «تقضي ب…» (a dam is water, a bridge on a road is a road); the examples, the
    law and the Constitution open their pages."""
    from apps.blog.services import expropriation
    meta = posts.meta('expropriation')
    figures = posts.figures('expropriation')
    rx = [(p['key'], expropriation.re.compile(p['re'])) for p in meta['purposes']]
    assert expropriation.purpose('مرسوم بإعلان أن المنفعة العامة تقضي ببناء سد واد اخفمان وبنزع ملكية القطع الأرضية', rx) == 'water'
    assert expropriation.purpose('مرسوم بإعلان أن المنفعة العامة تقضي بتهيئة محول الطريق الجهوية رقم 315 وبنزع ملكية', rx) == 'road'
    assert expropriation.purpose('مرسوم بإعلان أن المنفعة العامة تقضي بإحداث ثانوية أبي بكر الصديق وبنزع ملكية', rx) == 'school'
    assert all(v['viewer'] for v in figures['texts'].values())
    assert sum(sum(v for k, v in y.items() if k != 'year') for y in figures['years'] if y['year'] >= 2020) == 912


def test_the_grand_viziers_name_and_his_pages_are_tied():
    """«محمد المقري»: the clipping from BO 1000 and the titles he signed open their pages; the count is the title's."""
    meta = posts.meta('mokri')
    figures = posts.figures('mokri')
    assert all(v['viewer'] for v in figures['texts'].values())
    assert figures['texts']['clip']['issue'] == '1000'
    assert figures['total'] == 11679
    assert {y['resident'] for y in figures['years'] if y['year'] == 1931} == {'saint'}
    assert len(meta['residents']) == 12


def test_a_ministry_is_read_from_the_authority_without_its_minister_or_delegates():
    """«وزارة التعليم»: the person's name, «بالنيابة», delegates and second offices are set aside; a joint order names each
    portfolio."""
    from apps.blog.services import ministry
    assert ministry.portfolios('وزير التربية الوطنية (يوسف بلعباس)') == ['التربية الوطنية']
    assert ministry.portfolios('وزير التربية الوطنية بالنيابة') == ['التربية الوطنية']
    assert ministry.portfolios('الوزير المنتدب لدى وزير التربية الوطنية المكلف بالتعليم الثانوي') == []
    assert ministry.portfolios('وزير التربية الوطنية والتكوين المهني والتعليم العالي والبحث العلمي الناطق الرسمي باسم الحكومة') == ['التربية الوطنية والتكوين المهني والتعليم العالي والبحث العلمي']
    assert ministry.portfolios('وزير التعليم الابتدائي ووزير التعليم الثانوي والتقنى') == ['التعليم الابتدائي', 'التعليم الثانوي والتقنى']
    assert ministry.key('التعليم الثانوي و التقنى') == ministry.key('التعليم الثانوي والتقني')
    assert len(posts.figures('ministry')['names']) == 24


def test_each_extension_is_read_to_its_day_and_tied_to_its_page():
    """«حالة الطوارئ الصحية»: an extension's first article is read to its day («إلى غاية يوم الأحد «31 أكتوبر 2021»);
    every decree and the decree-law open their pages."""
    from datetime import date

    from apps.blog.services import emergency
    assert emergency.until('تمدد … إلى غاية يوم الأحد «31 أكتوبر 2021 في الساعة السادسة مساء') == date(2021, 10, 31)
    assert emergency.until('إلى غاية يوم 20 أبريل 2020 في الساعة السادسة مساء') == date(2020, 4, 20)
    figures = posts.figures('emergency')
    assert len(figures['terms']) == 33 and figures['terms'][-1]['until'] == '2023-02-28'
    assert all(v['viewer'] for v in figures['texts'].values())
