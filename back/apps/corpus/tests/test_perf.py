"""What the corpus's public answers cost in queries (S20 of the performance audit, 24 Oct 2026): a ceiling that does not
grow with the laws, articles or citations on the page. A query inside a loop breaks it."""
from datetime import date

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version, latest_ids

pytestmark = pytest.mark.django_db


def law(number: str, *, articles: int = 3, versions: tuple = (Consolidation.AS_PUBLISHED,), day=date(2020, 1, 1),
        title: str = '') -> Text:
    """A law with its versions (all starting `day`) and `articles` articles in each, the eids art_1…"""
    text = Text.objects.create(akn_uri=f'/akn/ma/act/loi/{number}', type='law', number=number,
                               number_as_printed=number.replace('-', '.'), title_ar=title or f'القانون رقم {number}')
    for consolidation in versions:
        v = Version.objects.create(text=text, language='ar', valid_from=day, consolidation=consolidation)
        for i in range(1, articles + 1):
            Article.objects.create(version=v, order=i, label=f'المادة {i}', number=str(i), eid=f'art_{i}',
                                   body=f'نص المادة {i} من {consolidation}.')
    return text


def test_the_texts_index_reads_anchors_in_a_few_queries(api, django_assert_max_num_queries):
    for n in range(8):
        law(f'{n + 10}-20', articles=n + 1)
    with django_assert_max_num_queries(3):
        d = api.get('/api/corpus/texts/').json()
    assert [len(t['articles']) for t in d] == list(range(1, 9))


def test_the_texts_index_lists_the_version_the_page_shows(api):
    # Two versions start the same day: Adala's consolidation stands before the BO's (RANK), as on the text's page.
    text = law('52-05', versions=(Consolidation.AS_PUBLISHED, Consolidation.ADALA))
    Article.objects.filter(version__text=text, version__consolidation=Consolidation.ADALA, order=3).update(eid='art_3-1')
    d = api.get('/api/corpus/texts/').json()
    assert d[0]['articles'] == ['art_1', 'art_2', 'art_3-1']
    assert text.latest_version().consolidation == Consolidation.ADALA


def test_a_version_not_yet_in_force_is_not_the_texts_version():
    # The health review, S3: Adala's copy of 65.00 holds law 54.23, in force from 1 Feb 2027; today's text is the
    # BO's chain. A text with only versions to come reads the soonest.
    text = law('65-00', day=date(2002, 11, 21))
    Version.objects.create(text=text, language='ar', valid_from=date(2025, 8, 25), consolidation=Consolidation.MACHINE)
    Version.objects.create(text=text, language='ar', valid_from=date(2099, 2, 1), consolidation=Consolidation.ADALA)
    assert text.latest_version().valid_from == date(2025, 8, 25)
    rows = text.versions.values_list('id', 'text_id', 'valid_from', 'consolidation')
    assert latest_ids(rows) == {text.id: text.latest_version().id}
    later = law('54-23', day=date(2099, 2, 1))
    Version.objects.create(text=later, language='ar', valid_from=date(2099, 3, 1), consolidation=Consolidation.MACHINE)
    assert later.latest_version().valid_from == date(2099, 2, 1)


def test_the_shelf_costs_three_queries_whatever_it_holds(api, django_assert_max_num_queries):
    # S5 of the performance audit: four queries a book before, the first a scan of every text.
    for number in ('31-08', '18-00', '12-90', '09-08', '31-13'):
        law(number, articles=4)
    with django_assert_max_num_queries(3):
        shelf = api.get('/api/corpus/shelf/').json()
    held = {b['key']: b for b in shelf if b['state'] == 'in_corpus'}
    assert sorted(held) == ['access_information', 'co_ownership', 'consumer', 'personal_data', 'urbanism']
    assert held['consumer']['articles'] == 4 and held['consumer']['path'] == '/ma/loi/31-08'


def test_the_situations_cost_six_queries(api, django_assert_max_num_queries, settings):
    settings.SHOW_DRAFTS = True       # the drafts too: every situation and every article it names
    law('31-08', articles=60)
    with django_assert_max_num_queries(6):
        assert api.get('/api/corpus/situations/').status_code == 200


def test_a_topic_page_costs_the_same_whatever_its_laws(api, django_assert_max_num_queries, settings):
    settings.SHOW_DRAFTS = True
    for number in ('31-08', '24-09', '09-08'):
        law(number, articles=30)
    with django_assert_max_num_queries(16):
        assert api.get('/api/topics/consumer/').status_code == 200


@pytest.mark.parametrize('cited', [4, 24])
def test_a_text_window_costs_the_same_whatever_it_cites(api, django_assert_max_num_queries, cited):
    # S3 of the performance audit: each cited law cost an alias, a law, its versions, an article and its whole change
    # list (467 queries on the finance law). The window's citations are now resolved together.
    for n in range(cited):
        law(f'{n + 1}-90', articles=3)
    citing = law('99-26', articles=0)
    v = citing.versions.get()
    for n in range(cited):
        Article.objects.create(version=v, order=n + 1, label=f'المادة {n + 1}', number=str(n + 1), eid=f'art_{n + 1}',
                               body=f'تطبق أحكام المادة 2 من القانون رقم {n + 1}.90 والقانون رقم {n + 1}.91 وظهير شريف رقم 1.11.{n}.')
    # 28 with nothing kept, as here: the version a request picks and its anchors name the kept answer (OP18), and both
    # are kept in their turn, so a kept window asks one query (test_kept).
    with django_assert_max_num_queries(28):
        d = api.get('/api/corpus/at/ma/loi/99-26/', {'window': 30}).json()
    links = [m for a in d['articles'] for m in a['marks'] if m['kind'] == 'link']
    assert len(links) == 3 * cited
    assert links[0] == {'start': links[0]['start'], 'end': links[0]['end'], 'kind': 'link', 'href': '/ma/loi/1-90/art_2',
                        'state': 'found', 'title': 'القانون رقم 1-90'}
    assert {m['state'] for m in links[1::3]} == {'not_in_corpus'}


@pytest.mark.parametrize('n', [3, 15])
def test_an_issue_and_its_pages_cost_the_same_whatever_its_texts(api, django_assert_max_num_queries, n):
    import hashlib

    from django.utils import timezone

    from apps.quality.models import Report
    from apps.sources.models import Document, Edition, Issue, Page, PageKind

    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=hashlib.sha256(b'7533').hexdigest(), path='x.pdf',
                                  mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now(), page_count=4)
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10), document=doc)
    for i in range(4):
        Page.objects.create(document=doc, index=i, printed_number=100 + i, kind=PageKind.TEXT_LAYER)
    for k in range(n):
        t = law(f'{k + 1}-26', articles=2)
        Text.objects.filter(pk=t.pk).update(first_published_in=issue, first_published_page=100)
        Version.objects.filter(text=t).update(source_pages='100-103')
        Report.objects.create(path=f'/ma/loi/{k + 1}-26/art_1', kind=Report.Kind.READING, status=Report.Status.OPEN)
    with django_assert_max_num_queries(5):
        assert len(api.get('/api/corpus/issues/general_ar/7533/').json()['texts']) == n
    with django_assert_max_num_queries(5):
        assert api.get('/api/corpus/issues/general_ar/7533/quality/').json()['open_reports'] == n
    with django_assert_max_num_queries(5):
        assert len(api.get(f'/api/sources/documents/{doc.pk}/pages/1/').json()['texts']) == n


def test_the_finance_laws_and_follows_news_cost_the_same_whatever_they_list(api, django_assert_max_num_queries):
    from apps.budget.models import FinanceLaw

    for year in range(2015, 2027):
        FinanceLaw.objects.create(year=year, kind='law', number=f'{year}', checks=[])
    with django_assert_max_num_queries(3):
        assert len(api.get('/api/budget/laws/').json()) == 12
    for n in range(6):
        law(f'{n + 1}-24', articles=2)
    paths = [f'/ma/loi/{n + 1}-24' for n in range(6)]
    with django_assert_max_num_queries(40):
        assert api.get('/api/follows/news/', {'path': paths}).status_code == 200


def test_a_shelf_number_is_found_with_or_without_its_leading_zero(api):
    # The shelf, 27 Oct 2026: BO 5711's reading numbers law 09.08 «09-08», Adala's «9-08»; either is the shelf's book.
    text = law('9-08', articles=2)
    assert {b['key']: b['state'] for b in api.get('/api/corpus/shelf/').json()}['personal_data'] == 'in_corpus'
    Text.objects.filter(pk=text.pk).update(number='09-08')
    from apps.corpus.services.generation import bump

    bump('corpus')
    assert {b['key']: b['state'] for b in api.get('/api/corpus/shelf/').json()}['personal_data'] == 'in_corpus'


def test_a_number_printed_on_another_cover_leads_to_it(api, django_assert_max_num_queries):
    """C1 of the mended-Bulletin review: /bo/general_ar/611 shows BO 610, «عدد 610 — 637», and says so."""
    import hashlib

    from django.utils import timezone

    from apps.sources.models import Document, Edition, Issue, Page, PageKind

    def bo(number, copy_of=None):
        doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=hashlib.sha256(str(number).encode()).hexdigest(),
                                      path=f'{number}.pdf', mime='application/pdf', language='ar', bytes=1,
                                      fetched_at=timezone.now(), page_count=1)
        return Issue.objects.create(edition=Edition.GENERAL_AR, number=number, date=date(1925, 1, 6), document=doc,
                                    copy_of=copy_of, first_page_number=1)

    cover = bo(610)
    Page.objects.create(document=cover.document, index=0, printed_number=1, kind=PageKind.SCAN)
    for n in (611, 637):
        bo(n, copy_of=cover)
    t = law('1-25', articles=1)
    Text.objects.filter(pk=t.pk).update(first_published_in=cover, first_published_page=1)
    with django_assert_max_num_queries(5):
        own = api.get('/api/corpus/issues/general_ar/610/').json()
    assert (own['key'], own['last_number'], own['asked_for']) == ('610', 637, None)
    copy = api.get('/api/corpus/issues/general_ar/611/').json()
    assert (copy['key'], copy['asked_for'], len(copy['texts'])) == ('610', '611', 1)
    listed = {i['key']: i['last_number'] for i in api.get('/api/corpus/issues/').json()}
    assert listed == {'610': 637}
