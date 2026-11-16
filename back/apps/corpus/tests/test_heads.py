"""A law's address answered with its own head (N5 of the read-and-trusted review): a link to an article previews as that
article, not as the home page. Since the search-engines review (9 Nov 2026): its words drawn by the app's components (IX1), a
404 where it leads nowhere (IX2), a 301 from an old address (IX3), Legislation markup and SITE_URL (IX8, IX9), and BO
issues and the words with heads of their own."""
import json
import re
from datetime import date
from unittest import mock

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.corpus.models import Alias, Article, Consolidation, Text, Version
from apps.sources.models import Document, Issue

pytestmark = pytest.mark.django_db
SHELL = ('<!doctype html><html lang="ar" dir="rtl"><head><title>قانون</title>\n'
         '    <meta name="description" content="قوانين المغرب مادة بمادة" />\n'
         '    <link rel="modulepreload" crossorigin href="/assets/a.js">\n</head><body><div id="root"></div></body></html>')


@pytest.fixture
def labour(tmp_path, settings):
    (tmp_path / 'index.html').write_text(SHELL)
    settings.WEB_DIST = str(tmp_path)
    settings.SITE_URL = 'https://3adala.com'
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', status='in_force',
                               signed_on=date(2003, 9, 11), title_ar='القانون رقم 65.99 المتعلق بمدونة الشغل')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 7, 16), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='المادة 65', number='65', eid='art_65',
                           body='يجب ، تحت طائلة سقوط الحق، رفع دعوى الفصل أمام المحكمة المختصة، في أجل تسعين يوما.')
    Article.objects.create(version=v, order=2, label='المادة 66', number='66', eid='art_66', body='يجب على المشغل.')
    return text


def ld(page: str) -> dict:
    return json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page).group(1))


def test_an_articles_address_previews_as_that_article(api, labour, settings):
    settings.ALLOWED_HOSTS = ['old.example.org']
    r = api.get('/ma/loi/65-99/art_65', HTTP_HOST='old.example.org', HTTP_X_FORWARDED_PROTO='https')
    page = r.content.decode()
    assert r.status_code == 200 and r['Content-Type'].startswith('text/html')
    assert '<title>مدونة الشغل · المادة 65 — قانون</title>' in page
    assert 'og:description" content="يجب ، تحت طائلة سقوط الحق' in page
    # On the site's address whatever host the request came by (IX9): a change of name is one setting.
    assert 'og:image" content="https://3adala.com/api/corpus/card/?path=/ma/loi/65-99/art_65"' in page
    assert '<link rel="canonical" href="https://3adala.com/ma/loi/65-99/art_65" />' in page
    assert page.count('name="description"') == 1                      # the shell's own description is gone
    assert '<div id="root"></div>' in page                            # nothing drawn without SSR_URL


def test_the_head_says_what_the_law_is(api, labour):
    # IX8: schema.org Legislation for every law, not only the 91 the deploy prerenders.
    text = ld(api.get('/ma/loi/65-99').content.decode())
    assert text['@type'] == 'Legislation' and text['legislationIdentifier'] == '/akn/ma/act/loi/65-99'
    assert text['legislationDate'] == '2003-09-11' and text['legislationLegalForce'] == 'InForce'
    assert text['url'] == 'https://3adala.com/ma/loi/65-99' and text['legislationJurisdiction'] == 'MA'
    article = ld(api.get('/ma/loi/65-99/art_65').content.decode())
    assert article['name'] == 'المادة 65 من مدونة الشغل'
    assert article['isPartOf']['url'] == 'https://3adala.com/ma/loi/65-99'


def test_a_title_says_what_a_decree_is_about(api, labour):
    # A cut title left «مرسوم رقم 2.73.176 — قانون», with no word of its subject; the date clause gives way to it.
    text = Text.objects.create(akn_uri='/akn/ma/act/decret/2-73-176', type='decree', number='2-73-176',
                               title_ar='مرسوم رقم 2.73.176 بتاريخ 27 ذي الحجة 1394 (10 يناير 1975) تحدد بموجبه لائحة '
                                        'الاشخاص المستفيدين من الاراضي الفلاحية (اقليم الجديدة)')
    v = Version.objects.create(text=text, language='ar', valid_from=date(1975, 1, 10))
    Article.objects.create(version=v, order=1, label='الفصل 1', number='1', eid='art_1', body='تحدد لائحة.')
    page = api.get('/ma/decret/2-73-176').content.decode()
    assert '<title>مرسوم رقم 2.73.176 تحدد بموجبه لائحة الاشخاص المستفيدين من الاراضي الفلاحية (اقليم الجديدة) — قانون' \
           '</title>' in page


def test_an_address_that_leads_nowhere_says_so(api, labour):
    # IX2: a 404, with the app (which says it in words); a crawler kept a 200 as a page.
    from apps.corpus.services.heads import flags
    r = api.get('/ma/loi/1-01')
    page = r.content.decode()
    assert r.status_code == 404 and flags() in page and page.replace(flags(), '') == SHELL
    assert api.get('/ma/loi/65-99/art_999').status_code == 404


def test_an_old_address_leads_to_the_texts_own(api, labour):
    # IX3: 26,761 aliases each answered as a page of its own; a slash at the end too.
    Alias.objects.create(alias='/akn/ma/act/loi/065-99', uri='/akn/ma/act/loi/65-99', reason='moved')
    r = api.get('/ma/loi/065-99/art_65?on=2024-01-01')
    assert r.status_code == 301 and r['Location'] == '/ma/loi/65-99/art_65?on=2024-01-01'
    r = api.get('/ma/loi/65-99/')
    assert r.status_code == 301 and r['Location'] == '/ma/loi/65-99'
    r = api.get(f'/texts/{labour.pk}')
    assert r.status_code == 301 and r['Location'] == '/ma/loi/65-99'
    assert api.get('/texts/999999').status_code == 404


@pytest.fixture
def drawing(settings):
    settings.SSR_URL = 'http://127.0.0.1:8043'
    with mock.patch('apps.seo.services.ssr.draw', return_value='<main><article>يجب ، تحت طائلة سقوط الحق</article></main>') as draw:
        yield draw


def test_a_law_is_drawn_with_its_words(api, labour, drawing):
    # IX1: the answer the app asks for (window=30), drawn by the app's components, under the law's head.
    page = api.get('/ma/loi/65-99/art_65').content.decode()
    assert '<div id="root" data-prerendered><main><article>يجب ، تحت طائلة سقوط الحق</article></main></div>' in page
    assert 'modulepreload' not in page                                # its words need not race the app's code
    path, seed = drawing.call_args.args
    assert path == '/ma/loi/65-99/art_65' and drawing.call_args.kwargs == {'one': 'art_65'}
    key, answer = seed[0]
    assert key == ['textAt', '/ma/loi/65-99', ''] and json.loads(answer)['focus'] == 'art_65'
    # The same kept bytes the API gives the app for it.
    assert answer == api.get('/api/corpus/at/ma/loi/65-99/art_65/', {'window': 30}).content


def test_drawn_words_spend_the_readers_day(api, labour, drawing, settings):
    # The words in the HTML are no way around the day of reading (apps/corpus/services/reading.py).
    cache.clear()
    settings.READING_BUDGET = 1
    first = api.get('/ma/loi/65-99/art_65', HTTP_CF_CONNECTING_IP='203.0.113.9').content.decode()
    later = api.get('/ma/loi/65-99/art_66', HTTP_CF_CONNECTING_IP='203.0.113.9').content.decode()
    assert 'data-prerendered' in first and 'data-prerendered' not in later
    assert '<title>مدونة الشغل · المادة 66 — قانون</title>' in later   # the head stays
    # A search engine's crawler from its published addresses reads on (IX10).
    google = api.get('/ma/loi/65-99/art_66', HTTP_CF_CONNECTING_IP='66.249.66.1').content.decode()
    assert 'data-prerendered' in google


def test_nothing_drawn_for_the_law_on_a_date_or_when_the_service_is_silent(api, labour, drawing, settings):
    assert 'data-prerendered' not in api.get('/ma/loi/65-99', {'on': '2024-01-01'}).content.decode()
    # A window of megabytes (a decision's table of parcels) goes with its head at once, never to the drawing service.
    settings.SSR_MOST = 100
    calls = drawing.call_count
    assert 'data-prerendered' not in api.get('/ma/loi/65-99').content.decode() and drawing.call_count == calls
    settings.SSR_MOST = 1_000_000
    drawing.return_value = ''
    assert '<div id="root"></div>' in api.get('/ma/loi/65-99').content.decode()


def test_a_law_page_asks_the_same_few_questions_whatever_the_law(api, labour, drawing, django_assert_num_queries):
    # The law's answer is the API's (its ceiling is 28, test_perf); the page adds the head and the text's lookup. A law
    # forty articles longer asks the same.
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    # A first page warms what a process keeps (the flags' «conversation lives», the demo accounts): asked once, then
    # the two counted pages differ by the law alone. Run alone, this test had counted that warm-up against the longer law.
    assert api.get('/ma/loi/65-99/art_65').status_code == 200
    with CaptureQueriesContext(connection) as short:
        assert api.get('/ma/loi/65-99/art_65').status_code == 200
    v = labour.versions.get()
    Article.objects.bulk_create([Article(version=v, order=10 + i, label=f'المادة {100 + i}', number=str(100 + i),
                                         eid=f'art_{100 + i}', body='نص.') for i in range(40)])
    with django_assert_num_queries(len(short)):
        assert api.get('/ma/loi/65-99/art_65').status_code == 200
    assert 5 < len(short) <= 32, len(short)


def test_an_issue_is_headed_as_the_issue_it_is(api, labour, settings):
    # IX8: «الجريدة الرسمية عدد 7556» was the bare «قانون».
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='h7556', path='BO_7556.pdf', bytes=1,
                                  mime='application/pdf', language='ar', page_count=1, fetched_at=timezone.now())
    issue = Issue.objects.create(edition='general_ar', number=7556, date=date(2026, 10, 29), document=doc)
    labour.first_published_in = issue
    labour.save()
    settings.SSR_URL = 'http://127.0.0.1:8043'
    with mock.patch('apps.seo.services.ssr.draw', return_value='<main>7556</main>') as draw:
        r = api.get('/bo/general_ar/7556')
    page = r.content.decode()
    assert r.status_code == 200
    assert '<title>الجريدة الرسمية عدد 7556 · 29 أكتوبر 2026 — قانون</title>' in page
    assert 'القانون رقم 65.99 المتعلق بمدونة الشغل' in page.split('</title>')[1].split('<link')[0]
    assert '<link rel="canonical" href="https://3adala.com/bo/general_ar/7556" />' in page
    assert '<div id="root" data-prerendered><main>7556</main></div>' in page
    # The app starts from the answer it was drawn from (main.tsx's #seed).
    seed = json.loads(re.search(r'<script type="application/json" id="seed">(.*?)</script>', page).group(1))
    assert seed[0][0] == ['issue', 'general_ar', '7556'] and seed[0][1]['number'] == 7556
    assert draw.call_args.args[0] == '/bo/general_ar/7556'
    assert api.get('/bo/general_ar/1').status_code == 404


def test_the_words_have_heads_of_their_own(api, labour):
    page = api.get('/words').content.decode()
    assert '<title>كلمات القانون — قانون</title>' in page and 'النفقة' in page
    assert '<title>النفقة — كلمات القانون — قانون</title>' in api.get('/words/nafaqa').content.decode()
    assert api.get('/words/no-such-word').status_code == 404


def test_a_search_previews_as_the_question_and_its_first_door(api, labour, settings):
    # HM5 of the hard-moment review: a search shared on WhatsApp previewed as the bare site.
    settings.SHOW_DRAFTS = True
    from apps.topics.services import kit
    kit.load.cache_clear()
    page = api.get('/search', {'q': 'طردوني من الخدمة'}).content.decode()
    assert '<title>«طردوني من الخدمة» — قانون</title>' in page
    assert '<script type="application/json" id="flags">{"open": ' in page        # HM17: what is open, not asked again
    assert 'https://3adala.com/api/topics/work/card/?item=journeys' in page
    plain = api.get('/search', {'q': 'zzzz'}).content.decode()
    assert '<title>«zzzz» — قانون</title>' in plain and 'og:image' not in plain
    assert api.get('/search').content.decode().startswith('<!doctype html>')


KEPT = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'heads-default'},
        'answers': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'heads-answers'}}


@pytest.fixture
def kept():
    from django.core.cache import caches
    from django.test import override_settings
    with override_settings(CACHES=KEPT):
        for name in KEPT:
            caches[name].clear()
        yield caches['answers']
        for name in KEPT:
            caches[name].clear()


def test_a_drawn_law_is_kept_beside_the_answer_it_came_from(api, labour, drawing, kept):
    # OP14 of the open-source audit: nothing drawn was kept, so each visit of a law not prerendered held a worker while
    # the service drew it again. The second visit draws nothing; a change to the corpus or a new build draws again.
    from apps.corpus.services import generation, heads
    first = api.get('/ma/loi/65-99/art_65').content.decode()
    again = api.get('/ma/loi/65-99/art_65').content.decode()
    assert drawing.call_count == 1 and 'data-prerendered' in again and again == first
    api.get('/ma/loi/65-99/art_66')
    assert drawing.call_count == 2                                   # another article is another page
    generation.bump('corpus')
    api.get('/ma/loi/65-99/art_65')
    assert drawing.call_count == 3
    with mock.patch.object(heads, 'build', return_value='another'):  # a deploy: its own components draw again
        api.get('/ma/loi/65-99/art_65')
    assert drawing.call_count == 4


def test_a_page_the_service_did_not_draw_is_never_kept(api, labour, drawing, kept):
    drawing.return_value = ''
    page = api.get('/ma/loi/65-99')
    assert page.status_code == 200 and '<div id="root"></div>' in page.content.decode()   # the head alone, as before
    drawing.return_value = '<main>المادة 65</main>'
    assert 'data-prerendered><main>المادة 65</main>' in api.get('/ma/loi/65-99').content.decode()
    assert drawing.call_count == 2


def test_an_issue_drawn_is_kept_too(api, labour, kept, settings):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='h7556', path='BO_7556.pdf', bytes=1,
                                  mime='application/pdf', language='ar', page_count=1, fetched_at=timezone.now())
    Issue.objects.create(edition='general_ar', number=7556, date=date(2026, 10, 29), document=doc)
    settings.SSR_URL = 'http://127.0.0.1:8043'
    with mock.patch('apps.seo.services.ssr.draw', return_value='<main>7556</main>') as draw:
        for _ in range(3):
            assert '<main>7556</main>' in api.get('/bo/general_ar/7556').content.decode()
    assert draw.call_count == 1
