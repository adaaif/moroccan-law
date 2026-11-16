"""The library's catalogue, a book's card and the compact map of the issues (the every-code review, LB3–LB7, LB10,
LB13): what each says, and what each costs in queries whatever it holds."""
import hashlib
from datetime import date

import pytest
from django.utils import timezone

from apps.consolidation.models import Change, Verb
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.services import library
from apps.sources.models import Document, Edition, Issue

pytestmark = pytest.mark.django_db


def law(number: str, *, kind: str = 'law', uri: str = '', articles: int = 3, day=date(2020, 1, 1),
        consolidation=Consolidation.AS_PUBLISHED, headings=None) -> Text:
    text = Text.objects.create(akn_uri=uri or f'/akn/ma/act/{"loi" if kind == "law" else kind}/{number}', type=kind,
                               number=number, number_as_printed=number.replace('-', '.'), title_ar=f'القانون رقم {number}')
    v = Version.objects.create(text=text, language='ar', valid_from=day, consolidation=consolidation)
    for i in range(1, articles + 1):
        Article.objects.create(version=v, order=i, label=f'المادة {i}', number=str(i), eid=f'art_{i}', body=f'نص المادة {i}.',
                               heading_path=(headings or {}).get(i, []))
    return text


def issue(number: int, day: date, *, suffix: str = '', edition=Edition.GENERAL_AR, pages: int = 4, first: int | None = None,
          copy_of=None) -> Issue:
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=hashlib.sha256(f'{edition}{number}{suffix}'.encode()).hexdigest(),
                                  path=f'BO_{number}.pdf', mime='application/pdf', language='ar', bytes=1,
                                  fetched_at=timezone.now(), page_count=pages)
    return Issue.objects.create(edition=edition, number=number, suffix=suffix, date=day, document=doc,
                                first_page_number=first, copy_of=copy_of)


def change(text: Text, by: str, on: date, *, state=Change.State.READ, verb=Verb.MODIFIED, number='5', issue_no=None) -> Change:
    return Change.objects.create(text_uri=text.akn_uri, source=Change.Source.READING, by_kind='law', by_number=by,
                                 by_uri=f'/akn/ma/act/loi/{by}', number=number, verb=verb, state=state, published_on=on,
                                 effective_on=on, issue=issue_no, page=12 if issue_no else None)


def test_the_catalogue_is_nine_piles_of_67_books_each_branch_on_its_general_text():
    branches = library.catalogue()['branches']
    assert len(branches) == 9
    assert sum(len(b['books']) for b in branches) == 67
    keys = [k for b in branches for k in (b['base'],) if k]
    assert keys == ['constitution', 'family', 'doc', 'penal', 'civil_procedure', 'commerce', 'labour', 'tax']
    for b in branches:
        assert [x['base'] for x in b['books']].count(True) == (1 if b['base'] else 0)
        if b['base']:
            assert b['books'][0]['key'] == b['base'] and b['books'][0]['base']
    # Every key names a book, every book once; the shelf's 20 are among them.
    every = [x['key'] for b in branches for x in b['books']]
    assert len(set(every)) == 67 and sum(1 for b in branches for x in b['books'] if x['shelf']) == 20
    assert {r['path'] for b in branches for r in b['replaced']} == {'/constitution', '/ma/dahir/1-57-343', '/ma/loi/1-74-447'}


def test_a_book_says_how_current_the_text_a_reader_opens_is(api, django_assert_max_num_queries):
    labour = law('65-99', articles=5, day=date(2021, 2, 9), consolidation=Consolidation.ADALA)
    change(labour, '21-26', date(2026, 7, 16))                              # after the version: it may not hold it yet
    change(labour, '22-26', date(2026, 8, 1), state=Change.State.UNCLEAR)    # not shown as fact: no part of it
    family = law('70-03', articles=4, day=date(2021, 7, 29))
    change(family, '65-21', date(2021, 7, 29))                              # the version's own day: it holds it
    change(family, '99-99', date(2099, 1, 1))                               # to come: not yet law
    law('1-77-339', kind='dahir', uri='/akn/ma/act/dahir/1977/1-77-339', articles=6, day=date(1977, 11, 4))
    Change.objects.create(text_uri='/akn/ma/act/dahir/1-77-339', source=Change.Source.READING, by_kind='law', by_number='50-25',
                          by_uri='/akn/ma/act/loi/50-25', number='4', verb=Verb.MODIFIED, state=Change.State.CONFIRMED,
                          published_on=date(2025, 12, 16), effective_on=date(2026, 1, 1))
    for n in ('31-08', '18-00', '12-90', '09-08', '31-13'):
        law(n, articles=2)
    with django_assert_max_num_queries(7):
        d = api.get('/api/corpus/library/').json()
    books = {x['key']: x for b in d['branches'] for x in b['books']}
    assert books['labour']['articles'] == 5 and books['labour']['path'] == '/ma/loi/65-99'
    assert books['labour']['version'] == {'from': '2021-02-09', 'kind': 'adala'}
    assert books['labour']['stale'] and books['labour']['last_change'] == '2026-07-16' and books['labour']['changes'] == 1
    assert not books['family']['stale'] and books['family']['last_change'] == '2021-07-29'
    # The customs code's changes are read against dahir 1.77.339's other entry (TWINS).
    assert books['customs']['stale'] and books['customs']['last_change'] == '2026-01-01' and books['customs']['articles'] == 6
    assert books['doc']['state'] == 'not_in_corpus' and books['doc']['path'] is None
    assert 'الديوانة' in books['customs']['aliases'] and books['finance_2026']['extra'] == '/budget/2026'


def test_a_books_card_says_how_to_cite_it_its_parts_and_its_last_change(api, django_assert_max_num_queries):
    bo = issue(4418, date(1996, 10, 3), first=2185, pages=80)
    heads = {1: ['الكتاب الأول: التاجر'], 2: ['الكتاب الأول: التاجر'], 3: ['الكتاب الثاني: الأصل التجاري'],
             4: ['الكتاب الثاني: الأصل التجاري'], 5: ['الكتاب الثالث: ' + 'كلمات ' * 30]}
    text = law('15-95', articles=5, day=date(2026, 1, 29), consolidation=Consolidation.ADALA, headings=heads)
    Text.objects.filter(pk=text.pk).update(first_published_in=bo, first_published_page=2187, title_ar='قانون رقم 15.95 يتعلق بمدونة التجارة')
    law('71-24', articles=1)
    change(text, '71-24', date(2026, 1, 29), issue_no=7478)
    change(text, '89-17', date(2019, 1, 21))
    with django_assert_max_num_queries(8):
        d = api.get('/api/corpus/library/card/', {'path': '/ma/loi/15-95'}).json()
    assert d['issue']['number'] == 4418 and d['page'] == 2187 and d['articles'] == 5
    assert 'الجريدة الرسمية عدد 4418' in d['citation']
    # A sentence taken for a heading stays in the part before it.
    assert [(p['heading'], p['eid'], p['articles']) for p in d['parts']] == [
        ('الكتاب الأول: التاجر', 'art_1', 2), ('الكتاب الثاني: الأصل التجاري', 'art_3', 3)]
    assert d['last']['number'] == '71.24' and d['last']['path'] == '/ma/loi/71-24' and d['last']['issue']['number'] == 7478
    assert d['changes'] == 2 and d['version']['kind'] == 'adala'
    assert api.get('/api/corpus/library/card/', {'path': 'x'}).status_code == 400
    assert api.get('/api/corpus/library/card/', {'path': '/ma/loi/1-01'}).status_code == 404


def decode(col: dict) -> list[dict]:
    """The map's columns back into rows, as the web reads them (features/corpus/library/map.ts)."""
    rows, number, day, first, pages = [], 0, 0, 0, 0
    suffix, last, held = dict(col['s']), dict(col['l']), set(col['z'])
    for i in range(len(col['n'])):
        number += col['n'][i]
        day += col['d'][i]
        first = col['f'][i] + (first + pages if first and pages else 0)
        pages = col['p'][i]
        rows.append({'number': number, 'day': day, 'texts': col['t'][i], 'pages': pages, 'first': first,
                     'suffix': suffix.get(i, 0), 'last': last.get(i, 0), 'held': i in held})
    return rows


def test_the_map_holds_every_issue_held_compact_and_in_two_queries(api, django_assert_max_num_queries):
    a = issue(7550, date(2026, 10, 8), first=7400, pages=60)
    b = issue(7551, date(2026, 10, 12), first=7460, pages=78)
    issue(7551, date(2026, 10, 13), suffix='bis', first=7538, pages=4)           # held without a text: a report
    d = issue(610, date(1925, 1, 6), pages=41)
    issue(611, date(1925, 1, 6), copy_of=d)                                       # a number on 610's cover
    f = issue(3, date(1912, 11, 15), edition=Edition.TRANSLATION_FR, pages=4)
    issue(4, date(1912, 11, 22), edition=Edition.TRANSLATION_FR, pages=4)         # French, no text: not drawn
    for k, i in enumerate((a, b, d, f)):
        t = law(f'{k + 1}-26', articles=1)
        Text.objects.filter(pk=t.pk).update(first_published_in=i)
    with django_assert_max_num_queries(2):
        m = api.get('/api/corpus/issues/map/').json()
    assert m['epoch'] == '1912-01-01'
    ar = decode(m['ar'])
    assert [(r['number'], r['suffix'], r['texts'], r['held']) for r in ar] == [(610, 0, 1, False), (7550, 0, 1, False),
                                                                              (7551, 0, 1, False), (7551, 1, 0, True)]
    assert ar[0]['last'] == 611 and ar[0]['day'] == (date(1925, 1, 6) - date(1912, 1, 1)).days
    assert [r['first'] for r in ar] == [0, 7400, 7460, 7538] and ar[2]['pages'] == 78
    fr = decode({**m['fr'], 'f': [0] * len(m['fr']['n'])})
    assert [(r['number'], r['texts']) for r in fr] == [(3, 1)]


def test_the_catalogue_says_the_newest_issues_as_they_are_and_the_dozen(api, settings, tmp_path):
    """W9 and C5 of the library-search review: the two newest issues with what they hold; one kept by its pages alone says
    what its own contents table prints; when the SGG was last asked comes from the nightly fetch's note."""
    from apps.sources.models import Page
    held = issue(7556, date(2026, 10, 29), first=7973)
    report = issue(7556, date(2026, 10, 30), suffix='bis', pages=226, first=8055)
    Page.objects.create(document=report.document, index=0, kind='text_layer', text_source='ocr', printed_number=8055, text=(
        'السنة الخامسة عشرة بعد المائة - عدد 7556 مكرر\n\nالجريدة الرسمية\n\nفهرست\n\nصفحة\n\nتقارير\n\n'
        'الهيئة الوطنية للنزاهة والوقاية من الرشوة ومحاربتها. - تقرير برسم سنة 2025.\n\n'
        'التقرير السنوي للهيئة الوطنية للنزاهة برسم سنة 2025 ................ 8056\n'))
    text = law('12-26')
    text.first_published_in = held
    text.save(update_fields=['first_published_in'])
    law('70-03')
    settings.CORPUS_DIR = tmp_path
    (tmp_path / 'reports').mkdir()
    (tmp_path / 'reports' / 'fetch_new_issues.json').write_text(
        '{"begun": {}, "finished": {}, "asked": {"at": "2026-11-10T04:00:07+00:00", "listed": 7830, "newest": "7556-bis", "newest_date": "2026-10-30"}}')
    d = api.get('/api/corpus/library/').json()
    assert [(x['key'], x['texts'], x['pages']) for x in d['newest']] == [('7556-bis', 0, 226), ('7556', 1, 4)]
    assert d['newest'][0]['about'] == 'الهيئة الوطنية للنزاهة والوقاية من الرشوة ومحاربتها. - تقرير برسم سنة 2025.'
    assert d['newest'][1]['about'] == ''
    assert d['asked'] == {'at': '2026-11-10T04:00:07+00:00', 'newest': '7556-bis', 'newest_date': '2026-10-30'}
    assert d['most'] == ['family']                      # of the dozen, the ones the site holds here
    # The issue's own page says the same, line by line, with the page each entry leads to.
    r = api.get('/api/corpus/issues/general_ar/7556-bis/').json()
    assert [(x['kind'], x['page']) for x in r['contents']] == [('rubric', None), ('heading', None), ('entry', 8056)]
    assert api.get('/api/corpus/issues/general_ar/7556/').json()['contents'] == []


def test_a_contents_table_is_read_as_printed_and_nothing_is_made_up():
    from apps.sources.services.contents import about, contents
    assert contents('عدد 6813 مكرر\nتقرير') == [] and about('') == ''
    page = 'فهرست صفحة\n\nإعلانات وبلاغات\n\nالجدول الوطني للخبراء القضائيين برسم سنة 2026 .......... 5728\n\n| الرباط | |\n'
    assert contents(page) == [{'kind': 'rubric', 'text': 'إعلانات وبلاغات', 'page': None},
                              {'kind': 'entry', 'text': 'الجدول الوطني للخبراء القضائيين برسم سنة 2026', 'page': 5728}]
    assert about(page) == 'الجدول الوطني للخبراء القضائيين برسم سنة 2026'
