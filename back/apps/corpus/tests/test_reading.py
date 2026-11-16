"""The reading API: a text at its address, its articles' links and defined terms, a preview, the reference
to copy, and the Word export."""
from datetime import date

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db


@pytest.fixture
def law():
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10))
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/12-26', type='law', number='12-26',
                               number_as_printed='12.26', title_ar='قانون رقم 12.26 يتعلق بالصحافة',
                               first_published_in=issue)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 8, 10),
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', printed_page=1112,
                           body='يقصد في مدلول هذا القانون بما يلي :\n- **الناشر** : كل مؤسسة صحافية ؛')
    Article.objects.create(version=v, order=2, label='المادة 2', number='2', eid='art_2', printed_page=1113,
                           body='يلتزم الناشر بأحكام المادة الأولى أعلاه وبالقانون رقم 88.13.')
    Article.objects.create(version=v, order=3, label='المادة 3', number='3', eid='art_3', printed_page=1113,
                           body='تغير على النحو التالي أحكام المادة 2 من القانون رقم 88.13 :')
    return text


def test_a_text_opens_at_its_address(api, law):
    r = api.get('/api/corpus/at/ma/loi/12-26/art_2/')
    assert r.status_code == 200
    d = r.json()
    assert d['path'] == '/ma/loi/12-26' and d['focus'] == 'art_2'
    assert d['articles'][1]['path'] == '/ma/loi/12-26/art_2'
    assert api.get('/api/corpus/at/ma/loi/99-99/').status_code == 404


def test_articles_carry_their_links_and_defined_terms(api, law):
    d = api.get('/api/corpus/at/ma/loi/12-26/').json()
    assert d['definitions'] == [{'term': 'الناشر', 'eid': 'art_1', 'definition': 'كل مؤسسة صحافية ؛'}]
    body = d['articles'][1]['body']
    marks = d['articles'][1]['marks']
    words = [(m['kind'], body[m['start']:m['end']]) for m in marks]
    assert ('term', 'الناشر') in words
    assert ('link', 'المادة الأولى') in words
    link = next(m for m in marks if body[m['start']:m['end']] == 'المادة الأولى')
    assert link['href'] == '/ma/loi/12-26/art_1'
    outside = next(m for m in marks if 'القانون رقم 88.13' in body[m['start']:m['end']])
    assert outside['state'] == 'not_in_corpus' and outside['href'] is None
    # An article that changes another text: its bare «المادة 2» is the other text's.
    amending = d['articles'][2]
    assert not any(m['kind'] == 'link' and (m.get('href') or '').endswith('art_2') for m in amending['marks'])


def test_the_reference_to_copy(api, law):
    d = api.get('/api/corpus/at/ma/loi/12-26/').json()
    assert d['articles'][1]['citation'] == ('المادة 2 من القانون رقم 12.26 يتعلق بالصحافة، '
                                            'الجريدة الرسمية عدد 7533 بتاريخ 10 غشت 2026، ص. 1113')


def test_an_assembled_text_cites_the_bulletin_never_a_compilers_page(api, db):
    # HM37 of the hard-moment review: art. 53 of the labour code was «…، ص. 27», page 27 of Adala's PDF.
    from django.utils import timezone

    from apps.sources.models import Document
    Issue.objects.create(edition=Edition.GENERAL_AR, number=5167, date=date(2003, 12, 8))
    doc = Document.objects.create(source='adala', kind='consolidated_text', path='adala/65-99.pdf', sha256='c' * 64, bytes=1,
                                  fetched_at=timezone.now(), mime='application/pdf', language='ar', page_count=1,
                                  meta={'as_of': '2026-07-16', 'first_issue': 5167, 'first_page': 3969})
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', number_as_printed='65.99',
                               title_ar='القانون رقم 65.99 المتعلق بمدونة الشغل')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 7, 16), consolidation=Consolidation.ADALA,
                               source_document=doc)
    Article.objects.create(version=v, order=1, label='المادة 53', number='53', eid='art_53', printed_page=27, body='نص.')
    d = api.get('/api/corpus/at/ma/loi/65-99/').json()
    assert d['articles'][0]['citation'] == ('المادة 53 من القانون رقم 65.99 المتعلق بمدونة الشغل، الجريدة الرسمية عدد 5167 '
                                            'بتاريخ 8 دجنبر 2003، ص. 3969 (نص بعد التعديلات، بوابة عدالة، 16 يوليوز 2026)')
    # Without the issue anywhere: the title and who assembled it, no page of their file.
    doc.meta = {'as_of': '2026-07-16'}
    doc.save()
    from apps.corpus.services.citing import citation_ar
    assert citation_ar(text, v.articles.get(), v) == ('المادة 53 من القانون رقم 65.99 المتعلق بمدونة الشغل '
                                                      '(نص بعد التعديلات، بوابة عدالة، 16 يوليوز 2026)')


def test_preview(api, law):
    d = api.get('/api/corpus/preview/', {'path': '/ma/loi/12-26/art_2'}).json()
    assert d['label'] == 'المادة 2' and d['excerpt'].startswith('يلتزم الناشر')
    assert api.get('/api/corpus/preview/', {'path': '/ma/loi/12-26/art_9'}).status_code == 404


def test_word_export(api, law):
    r = api.post('/api/corpus/export/', {'paths': ['/ma/loi/12-26/art_2', '/ma/x/art_1']}, format='json')
    assert r.status_code == 200
    assert r['Content-Type'].startswith('application/vnd.openxmlformats')
    assert r.content[:2] == b'PK'
    assert api.post('/api/corpus/export/', {'paths': []}, format='json').status_code == 400


def _compiled(number: str, articles: int):
    """A text held only from Adala's file, whose note names the issue that first printed it."""
    from django.utils import timezone

    from apps.sources.models import Document
    issue = 5000 + int(number.split('-')[0])
    Issue.objects.get_or_create(edition=Edition.GENERAL_AR, number=issue, defaults={'date': date(2003, 12, 8)})
    doc = Document.objects.create(source='adala', kind='consolidated_text', path=f'adala/{number}.pdf',
                                  sha256=number.ljust(64, 'c'), bytes=1, fetched_at=timezone.now(), mime='application/pdf',
                                  language='ar', page_count=1, meta={'as_of': '2026-07-16', 'first_issue': issue, 'first_page': 9})
    text = Text.objects.create(akn_uri=f'/akn/ma/act/loi/{number}', type='law', number=number,
                               title_ar=f'القانون رقم {number}')
    Version.objects.create(text=text, language='ar', valid_from=date(2020, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 7, 16), consolidation=Consolidation.ADALA,
                               source_document=doc)
    for n in range(1, articles + 1):
        Article.objects.create(version=v, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}', body=f'نص {n}.')
    return text


@pytest.mark.parametrize('texts', [1, 6])
def test_the_word_export_asks_the_same_queries_whatever_it_holds(api, law, texts, django_assert_max_num_queries):
    # OP15 of the open-source audit: three queries or more for each of up to 200 paths.
    from io import BytesIO

    from docx import Document as Word

    from apps.corpus.services.citing import citation_ar
    held = [_compiled(f'{10 + i}-03', 4) for i in range(texts)]
    paths = [f'/ma/loi/{t.number}/art_{n}' for t in held for n in range(1, 5)] + ['/ma/loi/12-26/art_2', '/ma/x/art_1',
                                                                                  '/ma/loi/12-26/art_9', '/ma/loi/12-26']
    with django_assert_max_num_queries(4):
        r = api.post('/api/corpus/export/', {'paths': paths}, format='json')
    assert r.status_code == 200
    lines = [p.text for p in Word(BytesIO(r.content)).paragraphs]
    first = held[0].latest_version()
    assert lines[:3] == ['المادة 1', 'نص 1.', citation_ar(held[0], first.articles.get(eid='art_1'), first)]
    assert 'عدد 5010' in lines[2]                                    # the issue the file's note names
    assert lines[-3:] == ['المادة 2', 'يلتزم الناشر بأحكام المادة الأولى أعلاه وبالقانون رقم 88.13.',
                          citation_ar(law, law.latest_version().articles.get(eid='art_2'), law.latest_version())]
    assert len(lines) == 3 * (4 * texts + 1)
    assert api.post('/api/corpus/export/', [{'paths': paths}], format='json').status_code == 400


@pytest.mark.needs('fribidi')
def test_a_link_preview_card(api, law, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    r = api.get('/api/corpus/card/', {'path': '/ma/loi/12-26/art_2'})
    assert r.status_code == 200 and r['Content-Type'] == 'image/png'
    body = b''.join(r.streaming_content)
    assert body[:8] == b'\x89PNG\r\n\x1a\n'
    assert api.get('/api/corpus/card/', {'path': '/ma/loi/12-26/art_9'}).status_code == 404
    assert len(list((tmp_path / 'cards').glob('*.png'))) == 1      # drawn once, kept


@pytest.mark.needs('fribidi')
def test_a_link_preview_card_waits_while_the_site_draws_others(api, law, settings, tmp_path):
    # OP15 of the open-source audit: drawn under the drawing limits (config/drawing.py); one drawn already is served.
    from config.caching import counters
    settings.CORPUS_DIR = tmp_path
    settings.DRAWING_AT_ONCE = 1
    counters.add('drawing:place:0', 1, timeout=60)
    try:
        r = api.get('/api/corpus/card/', {'path': '/ma/loi/12-26/art_2'})
        assert r.status_code == 503 and r.json() == {'errors': [{'field': 'picture', 'code': 'busy'}]}
        assert not (tmp_path / 'cards').exists()
    finally:
        counters.delete('drawing:place:0')
    assert api.get('/api/corpus/card/', {'path': '/ma/loi/12-26/art_2'}).status_code == 200


@pytest.mark.needs('fribidi')
def test_a_link_preview_card_reads_no_more_of_an_article_than_four_lines_hold(law, monkeypatch):
    # A decision's one article is a table of megabytes: its card read it whole to draw four lines.
    from apps.corpus.services import cards
    article = Article.objects.get(eid='art_2')
    article.body = 'يلتزم الناشر ' * 400_000
    seen = []
    monkeypatch.setattr(cards, '_plain', lambda body: seen.append(len(body)) or body)
    cards.draw_card(law, article)
    assert seen and max(seen) <= cards.BODY_MOST


def test_the_index_the_prerender_reads(api, law):
    d = api.get('/api/corpus/texts/').json()
    assert d == [{'path': '/ma/loi/12-26', 'updated_at': d[0]['updated_at'], 'articles': ['art_1', 'art_2', 'art_3']}]
    assert api.get('/api/corpus/at/ma/loi/12-26/').json()['total_articles'] == 3
