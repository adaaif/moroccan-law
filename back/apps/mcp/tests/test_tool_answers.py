"""What the tools answer for the texts that are not plain laws in force (a bill, a text held without its articles, a
translation, an official consolidation), for an article that changed, was repealed or is too long to give whole, for a
long outline, and for the runs, issues and references an assistant asks wrongly."""
from datetime import date

import pytest
from django.utils import timezone

from apps.consolidation.models import Change
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.mcp.services import law
from apps.sources.models import Document, Issue

pytestmark = pytest.mark.django_db
SITE = 'http://localhost:5190'


def held(uri, bodies, *, type='law', title='', issue=None, page=None, headings=None, **version):
    """A text and one version of it, an article a body (labelled «المادة n», n from 1), the rows made last first: the
    order read is the articles' own."""
    text = Text.objects.create(akn_uri=uri, type=type, number=uri.rsplit('/', 1)[1],
                               number_as_printed=uri.rsplit('/', 1)[1].replace('-', '.'), title_ar=title,
                               status='in_force', first_published_in=issue, first_published_page=page)
    v = Version.objects.create(text=text, language='ar', **{'valid_from': date(2020, 1, 2),
                                                            'consolidation': Consolidation.AS_PUBLISHED, **version})
    Article.objects.bulk_create(reversed([Article(version=v, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                                                  body=body, heading_path=(headings or {}).get(n, []))
                                          for n, body in enumerate(bodies, start=1)]))
    return text


def document(sha, **meta):
    return Document.objects.create(source='adala', kind='consolidation', sha256=sha * 64, path=f'adala/{sha}.pdf',
                                   mime='application/pdf', bytes=1, language='ar', fetched_at=timezone.now(), meta=meta)


def bo(number, day, suffix=''):
    """An issue of the Arabic general edition, with its file."""
    scan = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{number}{suffix}'.ljust(64, '0'),
                                   path=f'bo/{number}{suffix}.pdf', mime='application/pdf', bytes=1, language='ar',
                                   fetched_at=timezone.now())
    return Issue.objects.create(edition='general_ar', number=number, suffix=suffix, date=day, document=scan)


def test_a_bill_is_said_to_be_no_law_wherever_it_is_read():
    held('/akn/ma/act/projet-loi/60-26', ['تحدد مقادير الضريبة كما يلي.'], type='bill',
         title='مشروع قانون المالية رقم 60.26 للسنة المالية 2027', consolidation=Consolidation.BILL,
         valid_from=date(2026, 10, 20))
    item, served = law.fetch('/ma/projet-loi/60-26')
    meta = item['metadata']
    assert served == 0 and meta['law']['status'] == 'a bill filed in Parliament: not law'
    assert meta['note'] == 'A bill (projet de loi) as filed or voted in a chamber: it is not law.'
    assert meta['published_in'] is None                    # filed in Parliament, never printed in the Bulletin
    article = law.fetch('/ma/projet-loi/60-26/art_1')[0]
    assert article['metadata']['status'] == 'a bill filed in Parliament: not law' and 'note' not in article['metadata']


def test_a_text_held_without_its_articles_gives_its_facts_and_no_run():
    issue = bo(4400, date(1996, 6, 6))
    Text.objects.create(akn_uri='/akn/ma/act/decret/2-96-1', type='decree', number='2-96-1', number_as_printed='2.96.1',
                        title_ar='مرسوم رقم 2.96.1', first_published_in=issue, first_published_page=12)
    item, _ = law.fetch('/ma/decret/2-96-1')
    assert item['text'] == "3adala holds this text's title and publication, not its articles."
    meta = item['metadata']
    assert (meta['articles'], meta['version']) == (0, None)
    assert meta['published_in'] == {'bo': '4400', 'date': '1996-06-06', 'page': 12, 'url': f'{SITE}/bo/general_ar/4400'}
    with pytest.raises(law.Problem, match=r'^مرسوم رقم 2\.96\.1 has no article 1 in its current version \(0 articles\)'):
        law.fetch('/ma/decret/2-96-1/art_1')
    with pytest.raises(law.Problem, match=r'^3adala holds no version of مرسوم رقم 2\.96\.1\.$'):
        law.read_articles('/ma/decret/2-96-1')
    with pytest.raises(law.Problem, match=r'^3adala holds no version of مرسوم رقم 2\.96\.1 on 1990-01-01 \(it may not have '
                                          r'existed yet\)\.$'):
        law.read_articles('/ma/decret/2-96-1', on='1990-01-01')


def test_a_version_says_what_it_is_a_translation_or_an_official_consolidation_as_of_its_day():
    held('/akn/ma/act/decret/2-26-10', ['تطبق مقتضيات هذا المرسوم.'], title='مرسوم رقم 2.26.10',
         consolidation=Consolidation.TRANSLATION, translated_from='fr')
    version = law.fetch('/ma/decret/2-26-10/art_1')[0]['metadata']['version']
    assert version['official'] is False and version['note'].startswith('Arabic translated by AI from the official French')
    assert 'as_of' not in version
    held('/akn/ma/act/loi/31-08', ['يحدد هذا القانون حقوق المستهلك.'], title='القانون رقم 31.08',
         consolidation=Consolidation.ADALA, source_document=document('a', as_of='2025-12-31'))
    version = law.fetch('/ma/loi/31-08/art_1')[0]['metadata']['version']
    assert version['as_of'] == '2025-12-31' and version['note'].startswith('Consolidated text: unofficial')


def test_an_articles_changes_its_standing_and_its_older_french(labour):
    amending = Text.objects.create(akn_uri='/akn/ma/act/loi/12-10', type='law', number='12-10',
                                   number_as_printed='12.10', title_ar='القانون رقم 12.10 بتغيير مدونة الشغل')
    Change.objects.create(text_uri=labour.akn_uri, number='51', verb='modified', source='sgg', by_kind='law',
                          by_number='12-10', by_uri=amending.akn_uri, issue=5956, issue_bis=True, page=7,
                          published_on=date(2011, 7, 28))
    Change.objects.create(text_uri=labour.akn_uri, number='51', verb='words', source='reading', state='read',
                          by_kind='decree', by_number='2-12-5', issue=6100, page=3, published_on=date(2012, 11, 1),
                          effective_on=date(2013, 1, 1))
    for verb, by, issue, on in (('modified', '8-05', 5400, date(2006, 3, 2)), ('repealed', '14-12', 6200, date(2013, 10, 3))):
        Change.objects.create(text_uri=labour.akn_uri, number='53', verb=verb, source='sgg', by_kind='law', by_number=by,
                              issue=issue, page=9, published_on=on)
    meta = law.fetch('/ma/loi/65-99/art_51')[0]['metadata']
    assert meta['changes'] == [
        {'on': '2011-07-28', 'how': 'modified', 'by': 'القانون رقم 12.10 بتغيير مدونة الشغل', 'by_id': '/ma/loi/12-10',
         'bo': '5956-bis', 'page': 7},
        {'on': '2013-01-01', 'how': 'words', 'by': 'decree 2-12-5', 'by_id': None, 'bo': '6100', 'page': 3}]
    assert meta['status'] == 'in force'
    assert meta['french']['note'] == 'The Arabic changed after this French was printed: the Arabic is the text in force.'
    assert law.fetch('/ma/loi/65-99/art_52')[0]['metadata']['french'] is None          # the BO printed no French of it
    repealed = law.fetch('/ma/loi/65-99/art_53')[0]['metadata']
    assert repealed['status'] == 'repealed' and repealed['law']['status'] == 'in force'
    text, data, _ = law.read_articles('/ma/loi/65-99', start='53', count=1)
    assert 'المادة 53 — http://localhost:5190/ma/loi/65-99/art_53\n[الكتاب الأول' in text
    assert '(This article is repealed.)' in text and data['articles'][0]['status'] == 'repealed'


def test_an_article_too_long_is_cut_at_a_word_with_its_link_and_one_just_short_enough_is_whole():
    long_body, whole_body = 'المادة ' * 2000, 'أجر ' * 3000                   # 14,000 and 12,000 characters
    held('/akn/ma/act/loi/70-25', [long_body, whole_body], title='قانون المالية رقم 70.25')
    item = law.fetch('/ma/loi/70-25/art_1')[0]
    assert item['text'] == ' '.join(['المادة'] * 1714) + ' …'
    assert item['metadata']['cut'] == ('This article is 14000 characters; the first 12000 are given. Its whole text is '
                                       f'at {SITE}/ma/loi/70-25/art_1.')
    whole = law.fetch('/ma/loi/70-25/art_2')[0]
    assert whole['text'] == whole_body and 'cut' not in whole['metadata']
    text, _, _ = law.read_articles('/ma/loi/70-25', count=2)
    assert text.count('This article is 14000 characters') == 1 and 'This article is 12000' not in text


def test_a_long_outline_stops_at_150_lines_and_a_run_is_20_articles_at_most():
    headings = {n: ['القسم الأول'] for n in range(3, 153)}
    held('/akn/ma/act/loi/58-25', [f'نص المادة {n} في المسطرة.' for n in range(1, 153)], title='قانون المسطرة المدنية',
         headings=headings)
    item = law.fetch('/ma/loi/58-25')[0]
    lines = item['text'].split('\n')
    assert lines[0] == '152 articles; version in force since 2020-01-02.'
    assert lines[1] == '  المادة 1 (/ma/loi/58-25/art_1): نص المادة 1 في المسطرة.'
    assert lines[3] == '§ القسم الأول' and lines.count('§ القسم الأول') == 1
    assert lines[-2].startswith('  المادة 150 (') and lines[-1] == '… 2 more articles: read them with read_articles.'
    text, data, served = law.read_articles('/ma/loi/58-25', count=50)
    assert served == 20 and data['range'] == [1, 20] and data['next'] == '/ma/loi/58-25/art_21'
    assert text.endswith('Next: read_articles from 21 (132 more articles).')
    assert 'المادة 2 — http://localhost:5190/ma/loi/58-25/art_2\nنص المادة 2' in text      # no heading line before 3
    assert '[القسم الأول]\nنص المادة 3 في المسطرة.' in text
    assert law.read_articles('/ma/loi/58-25', count=0)[1]['range'] == [1, 10]


@pytest.mark.parametrize('start, first', [('51-1', 'المادة 51'), ('art_53', 'المادة 53'), (' 52 ', 'المادة 52')])
def test_a_run_starts_at_the_article_asked_or_at_the_one_its_number_names(labour, start, first):
    _, data, _ = law.read_articles('/ma/loi/65-99', start=start, count=1)
    assert data['articles'][0]['label'] == first


def test_a_run_says_where_it_ends_and_refuses_an_article_the_text_does_not_have(labour):
    text, data, served = law.read_articles('/ma/loi/65-99', start='53', count=5)
    assert (served, data['range'], data['next']) == (2, [5, 6], None) and 'Next:' not in text
    with pytest.raises(law.Problem, match=r'^No article 700 in this version of مدونة الشغل \(6 articles\)\.$'):
        law.read_articles('/ma/loi/65-99', start='700')


def test_get_bulletin_lists_the_latest_week_forty_texts_at_most_and_says_what_is_left():
    def issue(number, day, texts):
        made = bo(number, day)
        Text.objects.bulk_create(Text(akn_uri=f'/akn/ma/act/decret/2-26-{number}{n:02d}', type='decree',
                                      number=f'2-26-{number}{n:02d}', title_ar=f'مرسوم رقم {n}', first_published_in=made,
                                      first_published_page=n) for n in range(1, texts + 1))
    issue(7560, date(2026, 11, 9), 41)
    issue(7554, date(2026, 11, 3), 2)                         # six days before: the same week
    issue(7553, date(2026, 11, 2), 1)                         # seven days before: the week before
    data = law.bulletin()
    assert [(i['key'], i['count'], len(i['texts'])) for i in data['issues']] == [('7560', 41, 40), ('7554', 2, 0)]
    text = law.bulletin_text(data)
    assert '  … 1 more: get_bulletin with issue 7560 lists them all.' in text
    assert '  … 2 more: get_bulletin with issue 7554 lists them all.' in text
    for k in range(1, 6):                                     # one a day between them: six issues a week at most
        issue(7560 - k, date(2026, 11, 9 - k), 1)
    assert [i['key'] for i in law.bulletin()['issues']] == ['7560', '7559', '7558', '7557', '7556', '7555']
    assert len(law.bulletin('7560')['issues'][0]['texts']) == 41          # one issue lists all of its own


def test_get_bulletin_says_what_is_wrong_with_the_issue_asked():
    with pytest.raises(law.Problem, match=r'^3adala holds no issue of the Bulletin officiel yet\.$'):
        law.bulletin()
    bo(7533, date(2026, 8, 10), suffix='bis')
    assert law.bulletin('7533 BIS')['issues'][0]['key'] == '7533-bis'
    assert law.fetch('bo/7533-bis')[0]['text'] == 'This issue published no text 3adala holds.'
    with pytest.raises(law.Problem, match=r'^«the latest» is not an issue number: give it as 7533 or 7533-bis\.$'):
        law.bulletin('the latest')
    with pytest.raises(law.Problem, match=r'^No issue 7533 in the Bulletin officiel \(general_ar\) that 3adala holds\.$'):
        law.bulletin('7533')


def test_check_references_asks_for_a_list_and_a_date_it_can_read():
    for wrong in ([], 'المادة 51 من القانون رقم 65.99'):
        with pytest.raises(law.Problem, match=r'^Give the references as a list of short strings'):
            law.check_references(wrong)
    with pytest.raises(law.Problem, match=r'^«last year» is not a date: give it as YYYY-MM-DD\.$'):
        law.check_references(['المادة 51 من القانون رقم 65.99'], since='last year')
