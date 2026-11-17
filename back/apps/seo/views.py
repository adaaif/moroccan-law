"""robots.txt, the sitemaps and IndexNow's key (the search-engines review, 9 Nov 2026), and security.txt. nginx sends these
addresses here."""
import re
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone

from apps.seo.services import indexnow

# The crawlers that gather pages to train AI models are asked to keep away (C4 of the search-engines review: training no,
# answers yes). The answering ones (OAI-SearchBot, ChatGPT-User, Claude-SearchBot, Claude-User, PerplexityBot) cite and
# link to the article, and stay under `*`. Google-Extended is Gemini's training, never Google Search. The site's own
# fetchers read the robots.txt of the sites they fetch from and obey it too (apps/sources/services/fetch.py).
TRAINING = ['GPTBot', 'ClaudeBot', 'CCBot', 'Google-Extended', 'Applebot-Extended', 'Meta-ExternalAgent', 'Bytespider']

# What no crawler reads (IX5): people's words, voices and pictures, which a law's page asks for while Google renders it
# (D9, 19 Oct 2026: a case someone wrote about must not follow them on Google); accounts, sign-in, the admin, the MCP;
# the measures' door (apps.analytics), where a crawler rendering a page is no reader and would only be dropped.
# The discussion's own pages are not here: nginx says noindex on them, which a crawler only sees on a page it may
# fetch (a blocked address can still show in results as a bare link, and on /people/ that is a name).
# The Bulletin's printed pages one by one (/pages/<issue>/<page>, 430,056 addresses): a picture and no words, noindex
# already, and every law's page links to dozens of them. On 16 and 17 Nov 2026 Applebot asked for 125,000 of them while
# Googlebot had not yet read one law: a crawler's visits go to the law, not to learn «noindex» 430,000 times.
CLOSED = ['/api/discussion/', '/api/explain/', '/api/media/', '/api/follows/', '/api/auth/', '/api/oauth/', '/admin/',
          '/gate/', '/oauth/', '/mcp', '/api/measure/', '/pages/']


def robots(request):
    site = settings.SITE_URL.rstrip('/')
    lines = ['# قانون · 3adala.com: the law is open to every search engine and every answering assistant (apps/seo/views.py).',
             'User-agent: *', 'Allow: /', *[f'Disallow: {p}' for p in CLOSED], '',
             '# Crawlers that train AI models.', *[f'User-agent: {name}' for name in TRAINING], 'Disallow: /', '',
             f'Sitemap: {site}/sitemap.xml', '']
    response = HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=3600'
    return response


def _file(path: Path):
    if not path.is_file():
        raise Http404
    response = FileResponse(open(path, 'rb'), content_type='application/xml; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=3600'
    return response


def sitemap_index(request):
    return _file(Path(settings.SITEMAPS_DIR) / 'sitemap.xml')


def sitemap(request, name):
    if not re.fullmatch(r'[a-z]+-\d+\.xml', name):
        raise Http404
    return _file(Path(settings.SITEMAPS_DIR) / 'sitemaps' / name)


def indexnow_key(request):
    return HttpResponse(indexnow.key(), content_type='text/plain; charset=utf-8')


def security_txt(request):
    """/.well-known/security.txt (RFC 9116): where to report a flaw without a public issue, CONTACT_EMAIL. Without an
    address there is no file. Expires is written at each request, at midnight UTC a day short of a year ahead (the RFC
    asks for less than a year), so it never lapses while the address stands."""
    if not settings.CONTACT_EMAIL:
        raise Http404
    site = settings.SITE_URL.rstrip('/')
    expires = (timezone.now() + timedelta(days=364)).replace(hour=0, minute=0, second=0, microsecond=0)
    lines = [f'Contact: mailto:{settings.CONTACT_EMAIL}', f'Expires: {expires:%Y-%m-%dT%H:%M:%SZ}',
             'Preferred-Languages: ar, fr, en', f'Canonical: {site}/.well-known/security.txt', '']
    response = HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=86400'
    return response
