"""The sitemaps (IX4 and IX13 of the search-engines review, 9 Nov 2026): every address a search engine should know, in files of
at most 40,000, written by `write_sitemaps` (nightly and at each deploy) under SITEMAPS_DIR and served by apps.seo.views.

Opened in waves, two weeks apart from INDEXING_OPENED (Google starts every site at the same cautious crawl rate; a
wave's Page indexing report is read before the next):
  1  the pages people land on, the Bulletin's issues, the codes, laws, organic laws, decree-laws, dahirs, constitutions,
     conventions, circulars and the bill, and every article of the shelf's and the topics' named texts
  2  the decrees and the decisions
  3  the orders and the rest, and every article of every text of more than one (one article is its text's page)
`lastmod` is the day the text last changed, never the day the file was written: Google trusts it only while it is true,
and ignores `priority` and `changefreq` (none here). The scans' viewer (/pages/…) and the searches are left out (IX7)."""
from collections import defaultdict
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.corpus.models import Article, Text, Version, latest_ids
from apps.corpus.services.addresses import text_path
from apps.sources.models import Issue

PER_FILE = 40_000
CHUNK = 2_000
FIRST = {'law', 'organic_law', 'decree_law', 'dahir', 'constitution', 'convention', 'circular', 'bill'}
SECOND = {'decree', 'decision'}
# The pages a reader lands on that are not the law's: the deploy's drawn ones (the topics, their journeys, tools and
# pages, the blog) are found in the built app; these are the others, each with a head of its own (Django's for /words,
# the deploy's for the rest: web/scripts/prerender.mjs). Never an address that only leads elsewhere (/budget goes to
# the year's law) nor one answered with the bare shell: nginx says noindex on those.
PAGES = ['/', '/topics', '/library', '/codes', '/bo', '/new', '/words', '/places', '/budget/2026', '/budget/2027',
         '/about', '/open-source', '/blog']
# The groups in the order they are written, each with its wave.
GROUPS = {'pages': 1, 'issues': 1, 'laws': 1, 'codes': 1, 'decrees': 2, 'orders': 3, 'articles': 3}


def wave(today: date | None = None) -> int:
    """The waves open today: SITEMAP_WAVE when set; else one more every two weeks from INDEXING_OPENED; 1 before."""
    if settings.SITEMAP_WAVE:
        return settings.SITEMAP_WAVE
    try:
        opened = date.fromisoformat(settings.INDEXING_OPENED)
    except ValueError:
        return 1
    days = ((today or timezone.localdate()) - opened).days
    return max(1, min(3, 1 + days // 14))


def _drawn_pages() -> list[str]:
    """The landing pages the deploy drew (web/scripts/prerender.mjs writes each as <path>/index.html in the built app)."""
    root = Path(settings.WEB_DIST)
    found = []
    for kind in ('topics', 'blog'):
        for page in sorted((root / kind).rglob('index.html')) if (root / kind).exists() else []:
            found.append('/' + str(page.parent.relative_to(root)))
    return found


def _words() -> list[str]:
    from apps.explain.services import concepts
    return [f"/words/{c['slug']}" for c in concepts.load() if c.get('term')]


def _named_ids() -> set[int]:
    from apps.corpus.services import codes
    return {t.pk for t in codes.texts_of([k for k, _ in codes.SHELF + codes.MORE]).values() if t is not None}


def entries() -> dict[str, list[tuple[str, date | None]]]:
    """{group: [(address, lastmod or None)]}, every group whatever the wave. A fixed number of queries: the texts, their
    standing versions, their articles' anchors by chunks of versions, the issues."""
    groups: dict[str, list] = defaultdict(list)
    for path in dict.fromkeys([*PAGES, *_drawn_pages(), *_words()]):
        groups['pages'].append((path, None))
    issues = (Issue.objects.filter(Exists(Text.objects.filter(first_published_in=OuterRef('pk'))))
              .order_by('edition', 'number', 'suffix').values_list('edition', 'number', 'suffix'))
    for edition, number, suffix in issues:
        groups['issues'].append((f"/bo/{edition}/{number}{f'-{suffix}' if suffix else ''}", None))

    newest = latest_ids(Version.objects.order_by().values_list('id', 'text_id', 'valid_from', 'consolidation'))
    ids = sorted(newest.values())
    anchors: dict[int, list[str]] = defaultdict(list)
    for start in range(0, len(ids), CHUNK):
        for version_id, eid in (Article.objects.filter(version_id__in=ids[start:start + CHUNK])
                                .order_by('version_id', 'order').values_list('version_id', 'eid')):
            anchors[version_id].append(eid)
    named = _named_ids()
    texts = Text.objects.filter(pk__in=newest.keys()).order_by('id').values_list('id', 'akn_uri', 'type', 'updated_at')
    for pk, uri, kind, updated in texts:
        path = text_path(uri)
        day = timezone.localdate(updated) if updated else None
        groups['laws' if kind in FIRST else 'decrees' if kind in SECOND else 'orders'].append((path, day))
        eids = anchors[newest[pk]]
        if len(eids) > 1:
            for eid in eids:
                groups['codes' if pk in named else 'articles'].append((f'{path}/{eid}', day))
    return groups


def _urlset(site: str, rows: list[tuple[str, date | None]]) -> str:
    lines = [f'<url><loc>{escape(site + path)}</loc>{f"<lastmod>{day.isoformat()}</lastmod>" if day else ""}</url>'
             for path, day in rows]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + '\n'.join(lines) + '\n</urlset>\n')


def write(directory: Path | None = None, today: date | None = None) -> dict:
    """Write every group's files and the index of the open waves' files; a file of the last run no group wrote is
    removed. Returns {'wave', 'files': {name: addresses}, 'listed': [names]}."""
    directory = Path(directory or settings.SITEMAPS_DIR)
    (directory / 'sitemaps').mkdir(parents=True, exist_ok=True)
    site = settings.SITE_URL.rstrip('/')
    open_wave = wave(today)
    written: dict[str, int] = {}
    listed: list[str] = []
    found = entries()
    for group, group_wave in GROUPS.items():
        rows = found.get(group, [])
        for n, start in enumerate(range(0, len(rows), PER_FILE), start=1):
            name = f'{group}-{n}.xml'
            _replace(directory / 'sitemaps' / name, _urlset(site, rows[start:start + PER_FILE]))
            written[name] = len(rows[start:start + PER_FILE])
            if group_wave <= open_wave:
                listed.append(name)
    for old in (directory / 'sitemaps').glob('*.xml'):
        if old.name not in written:
            old.unlink()
    index = ('<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
             + '\n'.join(f'<sitemap><loc>{site}/sitemaps/{name}</loc></sitemap>' for name in listed)
             + '\n</sitemapindex>\n')
    _replace(directory / 'sitemap.xml', index)
    return {'wave': open_wave, 'files': written, 'listed': listed}


def _replace(path: Path, content: str) -> None:
    tmp = path.with_suffix('.tmp')
    tmp.write_text(content, encoding='utf-8')
    tmp.replace(path)
