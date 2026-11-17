"""A law's address answered with the app's page and that law's own head (N5 of the read-and-trusted review, 27 Oct
2026): its name and article as the title («مدونة الشغل · المادة 65 — قانون»), its first words as the description, its
link picture. Every address had answered the same shell titled «قانون», so a link to art. 65 previewed on WhatsApp
as the home page. nginx sends a law's address here when no prerendered file exists for it (deploy/nginx.conf); the
prerender (web/scripts/prerender.mjs) writes the same head with the law's words for the texts read most.

Since the search-engines review (9 Nov 2026) the page holds the law too (IX1): the answer the app asks for (the same kept
bytes as /api/corpus/at…?window=30) drawn by the app's own components (web/scripts/ssr-server.mjs, the law-ssr
service), marked prerendered so the app fetches that answer and mounts over the same words. About 192,000 texts and
their articles had reached a crawler as an empty page. The words count against the reader's day like the API's
(apps/corpus/services/reading.py); past it, or when the drawing service does not answer, the head alone, as before.
What is drawn is kept beside the answer it was drawn from (its key, which carries the corpus's generation and the day)
and the build that drew it: a second request for the same law draws nothing. Nothing was kept before, so every visit
of a law not prerendered held a worker while the service drew it again.
A law's address that leads nowhere answers 404 (IX2); an old address of a text answers 301 to its own (IX3); the
head carries schema.org Legislation (IX8) and every address is written on SITE_URL, never the host a request came by
(IX9). BO issues and the words' pages get heads of their own (IX8)."""
import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponse, HttpResponsePermanentRedirect

from apps.corpus.services import codes, generation, reading
from apps.corpus.services.addresses import split_path, text_path
from apps.corpus.services.citing import MONTHS_AR
from apps.corpus.services.works import text_at

_SHELL: dict = {'mtime': None, 'html': '', 'build': ''}
# What the app asks for a law (web/src/features/corpus/corpus.api.ts, ARTICLE_WINDOW): the page is drawn from the same.
WINDOW = 30
# A title's date clause («صادر في 14 من رجب 1424 (11 سبتمبر 2003)», «بتاريخ … (…)»): a search result has room for the
# subject, not the date.
DATED = re.compile(r'\s+(?:ال)?(?:صادر|بتاريخ)\s+(?:في\s+)?[^()]{1,60}\([^)]{4,40}\)')
FORCE = {'in_force': 'InForce', 'partly_repealed': 'PartiallyInForce', 'repealed': 'NotInForce',
         'not_yet_in_force': 'NotInForce'}


def site() -> str:
    """The site's address, the one every canonical, card and sitemap names (IX9)."""
    return settings.SITE_URL.rstrip('/')


def shell() -> str:
    """The built app's index.html, read again when a deploy replaces it."""
    path = Path(settings.WEB_DIST) / 'index.html'
    mtime = path.stat().st_mtime
    if mtime != _SHELL['mtime']:
        page = path.read_text()
        _SHELL.update(mtime=mtime, html=page, build=hashlib.sha1(page.encode(), usedforsecurity=False).hexdigest()[:12])
    return _SHELL['html']


def build() -> str:
    """Which build of the app is served (its index.html names each of its files by a hash): part of a drawn page's key,
    so a deploy draws the pages again with its own components."""
    shell()
    return _SHELL['build']


def flags() -> str:
    """What is open, as /api/auth/register/ says it, carried by the page so the app need not ask (HM17 of
    the hard-moment review: a cold page made that request each visit)."""
    from apps.accounts.services import google
    from apps.discussion.services import counters
    on = {'open': settings.REGISTRATION_OPEN, 'discussion': settings.DISCUSSION_OPEN,
          'talk_alive': settings.DISCUSSION_OPEN and counters.alive(), 'mcp_open': settings.MCP_AUTH != 'required',
          'google': google.client_id()}
    return f'<script type="application/json" id="flags">{json.dumps(on)}</script>'


def _flagged(page: str) -> str:
    return page.replace('</body>', f'{flags()}</body>', 1)


def plain(s: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'\*\*|\||-{3,}', ' ', s)).strip()


def cut(s: str, n: int) -> str:
    """`s` in at most `n` characters, ending on a whole word."""
    if len(s) <= n:
        return s
    head = s[:n]
    words = head.split()
    if head[-1:].isspace():
        head = head.rstrip()
    elif words and len(words[-1]) < len(head):           # a word cut short goes, with the space before it
        head = head[:-len(words[-1])].rstrip()
    return head + '…'


def day_ar(d) -> str:
    return f'{d.day} {MONTHS_AR[d.month - 1]} {d.year}' if d else ''


def head_name(text) -> str:
    """The text's name for a title: its everyday or popular name when it has one; else its title without the date
    clause, which a cut title had left as «مرسوم رقم 2.73.176» alone, with no word of what it is about."""
    name = codes.display_name(text)['ar']
    full = (text.title_ar or '').strip()
    if full.startswith(name) and len(full) > len(name) + 8:
        return DATED.sub('', full, count=1).strip()
    return name


def legislation(text, name: str, path: str, article=None) -> dict:
    """schema.org Legislation for a text or one of its articles (IX8): what the page is, to any engine. The prerender
    writes the same for the named texts."""
    ld = {'@context': 'https://schema.org', '@type': 'Legislation', 'name': name,
          'legislationIdentifier': text.akn_uri, 'legislationType': text.get_type_display(),
          'legislationJurisdiction': 'MA', 'inLanguage': 'ar', 'url': f'{site()}{path}'}
    if text.signed_on:
        ld['legislationDate'] = text.signed_on.isoformat()
    if text.status in FORCE:
        ld['legislationLegalForce'] = FORCE[text.status]
    if article is not None:
        whole = text_path(text.akn_uri)
        ld = {**ld, 'name': f'{article.label} من {name}',
              'isPartOf': {'@type': 'Legislation', 'name': name, 'url': f'{site()}{whole}',
                           'legislationIdentifier': text.akn_uri}}
    return ld


def tags(path: str) -> dict | None:
    """{title, description, ld} for a law's address; None when it leads to no text or no such article."""
    uri, eid = split_path(path)
    text, _ = text_at(uri)
    if text is None:
        return None
    name = head_name(text)
    version = text.latest_version()
    articles = version.articles if version is not None else None
    if eid:
        article = articles.filter(eid=eid).only('label', 'number', 'body').first() if articles is not None else None
        if article is None:
            return None
        # An article people know by a name (F10 of the famous-articles review): the name in its title, its description and its
        # markup, so «الفصل 490 العلاقات الرضائية» on a search engine lands on the article.
        from apps.search.services.famous import of_text
        known = of_text(text_path(text.akn_uri)).get(article.number or '')
        said = (known or {}).get('ar') or []
        ld = legislation(text, name, path, article)
        if known and (said or known.get('fr')):
            ld['alternateName'] = [*said, *known.get('fr', [])]
        if said:
            return {'title': f'{article.label} من {cut(name, 70)}: {said[0]} — قانون',
                    'description': cut(f'يُعرف في النقاش العام بـ«{said[0]}». {plain(article.body)}', 160), 'ld': ld}
        return {'title': f'{cut(name, 90)} · {article.label} — قانون', 'description': cut(plain(article.body), 160),
                'ld': ld}
    first = articles.only('body').first() if articles is not None else None
    return {'title': f'{cut(name, 110)} — قانون', 'description': cut(plain(first.body if first else text.title_ar), 160),
            'ld': legislation(text, name, path)}


def _canonical(uri: str, eid: str) -> str:
    return text_path(uri) + (f'/{eid}' if eid else '')


def _kept_drawing(path: str, seed: list, answer: HttpResponse, one: str = '') -> str:
    """The page at `path` drawn from `seed`, whose answer is `answer`: kept beside it, under its key (its ETag, which
    carries the generations it was made of and the day) and the app's build, so a second request draws nothing. '' when
    the service drew nothing, which is never kept: the next request asks again."""
    from apps.seo.services import ssr

    tag = answer.get('ETag')
    if not tag:                 # the answer itself is not kept (no answers' cache): neither is its page
        return ssr.draw(path, seed, one=one)
    return generation.kept(['drawn', path, one, tag, build()], lambda: ssr.draw(path, seed, one=one) or None,
                           size=len) or ''


def _drawn(request, path: str, uri: str, eid: str, text) -> str:
    """The law drawn by the app's components, '' when it is not (no drawing service, the law on a date, the reader's
    day reached, the service silent)."""
    from apps.corpus.api.views import text_answer

    if not settings.SSR_URL or request.GET.get('on') or reading.reached(request):
        return ''
    answer, given = text_answer(text, eid, window=WINDOW)
    if len(answer.content) > settings.SSR_MOST:
        # A window of megabytes (an article can be one long table) would take the drawing service past its time, and it
        # would go on drawing after Django had stopped waiting: the head alone, at once.
        return ''
    drawn = _kept_drawing(path, [(['textAt', text_path(uri), ''], answer.content)], answer, one=eid)
    if drawn:
        # An article's page holds that article alone (the app brings its neighbours): one article read; a text's, its
        # first window.
        reading.spend(request, 1 if eid else given)
    return drawn


def law(request) -> HttpResponse:
    """GET /ma/…: a law's page (the view, apps/corpus/api/views.py law_page)."""
    uri, eid = split_path(request.path)
    text, now = text_at(uri)
    if text is None:
        return _missing()
    canonical = _canonical(now, eid)
    if request.path != canonical:
        # An address the text had before 19 Oct 2026, a twin merged into it, its promulgating dahir, a number written
        # with its leading zeros (26,761 of them answered as pages of their own), a slash at the end.
        query = request.META.get('QUERY_STRING')
        return HttpResponsePermanentRedirect(canonical + (f'?{query}' if query else ''))
    found = generation.kept(['head', 2, canonical], lambda: tags(canonical), scopes=('corpus',))
    if not found:
        return _missing()
    body = _drawn(request, canonical, uri, eid, text)
    return _answer(_headed(found, canonical, f'{site()}/api/corpus/card/?path={quote(canonical)}', body))


def _missing() -> HttpResponse:
    """A law's address that leads nowhere: the app says so (NotFound), and the status says it to a crawler (IX2)."""
    return _answer(_flagged(shell()), status=404)


def _answer(page: str, status: int = 200) -> HttpResponse:
    response = HttpResponse(page, content_type='text/html; charset=utf-8', status=status)
    response['Cache-Control'] = 'no-cache'
    return response


def search_tags(q: str) -> dict:
    """{title, description, card} for a search: the question as typed, and what its first door says (HM5 of
    the hard-moment review: a search shared on WhatsApp previewed as the bare site)."""
    from apps.topics.services import kit
    asked = cut(plain(q), 90)
    doors = kit.matching(q)[:1]
    if doors:
        d = doors[0]
        lead = (d.get('lead') or {}).get('ar') or ''
        return {'title': f'«{asked}» — قانون', 'description': cut(f"{d['title']['ar']}: {lead}" if lead else d['title']['ar'], 160),
                'card': f"/api/topics/{d['topic']}/card/?item={quote(d['ref'])}" if d.get('ref') else f"/api/topics/{d['topic']}/card/"}
    return {'title': f'«{asked}» — قانون', 'description': 'الجواب من نص القانون كما نُشر في الجريدة الرسمية، مادة مادة.', 'card': None}


def search_page(q: str) -> str:
    """The shell with a search's head, for /search?q=…; the shell as built for an empty question. Never indexed
    (nginx says noindex on /search, IX7): a search's page is one of endless ones."""
    q = q.strip()[:200]
    if not q:
        return _flagged(shell())
    found = search_tags(q)      # a few milliseconds: the doors are in memory
    return _headed(found, f'/search?q={quote(q)}', f"{site()}{found['card']}" if found.get('card') else None)


def issue(request, edition: str, key: str) -> HttpResponse:
    """GET /bo/<edition>/<key>: a Bulletin issue's page, headed as the issue it is («الجريدة الرسمية عدد 7556 — قانون»
    was the bare «قانون», IX8) and drawn with its list of texts."""
    from django.http import Http404

    from apps.corpus.api.views import IssueDetail

    try:
        answer = generation.answer(['issue', edition, key], lambda: IssueDetail.issue(edition, key))
    except Http404:
        return _missing()
    found = json.loads(answer.content)
    if found.get('asked_for'):
        # A number printed on another issue's cover: that issue's page (C1 of the mended-Bulletin review).
        return HttpResponsePermanentRedirect(f"/bo/{found['edition']}/{found['key']}")
    path = f'/bo/{edition}/{key}'
    label = 'Bulletin officiel' if edition.endswith('_fr') else 'الجريدة الرسمية'
    number = f"{found['number']}{' مكرر' if found.get('suffix') else ''}"
    texts = found.get('texts') or []
    day = day_ar(date.fromisoformat(found['date'])) if found.get('date') else ''
    description = cut('، '.join(cut(t.get('title') or '', 80) for t in texts[:3] if t.get('title')) or
                      f'{len(texts)} نصا', 160)
    head = {'title': f'{label} عدد {number}{f" · {day}" if day else ""} — قانون', 'description': description}
    seed = [(['issue', edition, key], answer.content)]
    body = _kept_drawing(path, seed, answer)
    return _answer(_headed(head, path, None, body, seed=seed if body else None))


def words(request, slug: str = '') -> HttpResponse:
    """GET /words and /words/<slug>: the words that open the law, headed as what they are (IX8)."""
    from apps.explain.services import concepts, explanations

    if not slug:
        terms = [c['term']['ar'] for c in concepts.load() if c.get('term')]
        head = {'title': 'كلمات القانون — قانون',
                'description': cut('معنى الكلمات التي يفتح بها القانون: ' + '، '.join(terms), 160)}
        return _answer(_headed(head, '/words', None))
    concept = concepts.find(slug)
    if concept is None or concept.get('built_in') or not concept.get('term'):
        return _missing() if concept is None else _answer(_flagged(shell()))
    term = concept['term']['ar']
    meaning = (explanations.word_meanings().get(slug) or {}).get('ar') or ''
    head = {'title': f'{term} — كلمات القانون — قانون',
            'description': cut(plain(meaning), 160) if meaning else cut(f'«{term}» في القانون المغربي: معناها والمواد التي تذكرها.', 160)}
    return _answer(_headed(head, f'/words/{slug}', None))


def _headed(found: dict, path: str, card: str | None, body: str = '', seed: list | None = None) -> str:
    base = shell()
    esc = lambda s: html.escape(s, quote=True)
    url = f'{site()}{esc(path)}'
    ld = found.get('ld')
    # `<` escaped: the JSON sits in an HTML script.
    marked = json.dumps(ld, ensure_ascii=False).replace('<', '\\u003c') if ld else ''
    head = '\n    '.join([
        f'<title>{esc(found["title"])}</title>',
        f'<meta name="description" content="{esc(found["description"])}" />',
        f'<link rel="canonical" href="{url}" />',
        '<meta property="og:site_name" content="قانون" />', '<meta property="og:locale" content="ar_MA" />',
        '<meta property="og:type" content="article" />',
        f'<meta property="og:title" content="{esc(found["title"])}" />',
        f'<meta property="og:description" content="{esc(found["description"])}" />',
        f'<meta property="og:url" content="{url}" />',
        *([f'<meta property="og:image" content="{esc(card)}" />',
           '<meta property="og:image:width" content="1200" />', '<meta property="og:image:height" content="630" />',
           '<meta name="twitter:card" content="summary_large_image" />'] if card else []),
        *([f'<script type="application/ld+json">{marked}</script>'] if marked else [])])
    base = re.sub(r'\s*<meta name="description"[^>]*>', '', base, count=1)
    page = re.sub(r'<title>[^<]*</title>', lambda _: head, base, count=1)
    if body:
        # The words are on the page: the app's code need not race the stylesheet for a slow line (the prerender's N5).
        page = re.sub(r'\s*<link rel="modulepreload"[^>]*>', '', page)
        page = page.replace('<div id="root"></div>', f'<div id="root" data-prerendered>{body}</div>', 1)
        if seed:
            # The answers it was drawn from: the app starts from them and mounts once its page's code has come (main.tsx).
            answers = b'[' + b','.join(b'[' + json.dumps(k).encode() + b',' + d + b']' for k, d in seed) + b']'
            page = page.replace('</body>', '<script type="application/json" id="seed">'
                                f"{answers.decode('utf-8').replace('<', chr(92) + 'u003c')}</script></body>", 1)
    return _flagged(page)
