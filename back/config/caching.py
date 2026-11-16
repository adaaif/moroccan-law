"""What a public answer says about being kept (S17 of the performance audit, 24 Oct 2026; no answer but the card picture
said anything before). An anonymous reader's answer to a public read may be kept by the browser and a proxy: the law a
minute (ten more while it is asked again), the discussion ten seconds (a minute more), a page's picture and files a
day. An answer to a signed-in request is never marked: it may hold what that reader wrote or voted. An answer to a
request with a key (X-Api-Key) is marked private whatever its view said, on every door (the site's API, the edition,
the versioned API): a cache in front of the site would otherwise hand one holder's answer, or download, and its counts
to the next caller. The ETag that lets a browser ask «has it changed?» comes from ConditionalGetMiddleware, or from the
kept answer's key."""
from django.utils.cache import patch_vary_headers

LAW = 'public, max-age=60, stale-while-revalidate=600'
TALK = 'public, max-age=10, stale-while-revalidate=60'
# A topic and its pages are written by the team and change with a check or an edit: five minutes, then a day in which
# the browser shows what it has at once and asks again behind it (26 Oct 2026: the topics are editorial and mostly
# static). A topic's two open questions may be a visit late.
TOPICS = 'public, max-age=300, stale-while-revalidate=86400'
POLICIES = (
    ('/api/sources/', 'public, max-age=86400'),
    ('/api/discussion/', TALK),
    ('/api/topics/', TOPICS),
    ('/api/corpus/', LAW), ('/api/search/', LAW), ('/api/budget/', LAW), ('/api/open/', LAW),
    ('/api/explain/', LAW), ('/api/follows/news/', LAW),
    # The measures' list for /privacy (apps.analytics): it changes with a deploy.
    ('/api/measure/', LAW),
)
# Reads that answer one person, whoever asks.
PRIVATE = ('/api/discussion/letters/', '/api/discussion/me/', '/api/discussion/review/', '/api/explain/at/')
KEY = 'HTTP_X_API_KEY'


def policy(request) -> str | None:
    if 'HTTP_AUTHORIZATION' in request.META or request.path.startswith(PRIVATE) or request.path.endswith('/review/'):
        return None
    return next((p for prefix, p in POLICIES if request.path.startswith(prefix)), None)


def keyed(request, response):
    """A keyed request's answer: private, the policy's or its view's times kept; `no-store` stays as it was."""
    said = [part.strip() for part in response.get('Cache-Control', '').split(',') if part.strip()]
    if not said and request.method in ('GET', 'HEAD') and response.status_code == 200:
        said = [part.strip() for part in (policy(request) or '').split(',') if part.strip()]
    said = [part for part in said if part.lower() != 'public']
    if not any(part.lower() in ('private', 'no-store') for part in said):
        said.insert(0, 'private')
    response['Cache-Control'] = ', '.join(said)
    patch_vary_headers(response, ('X-Api-Key',))
    return response


class PublicCaching:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.META.get(KEY, '').strip():
            return keyed(request, response)
        if request.method in ('GET', 'HEAD') and response.status_code == 200 and not response.has_header('Cache-Control'):
            kept = policy(request)
            if kept:
                response['Cache-Control'] = kept
                patch_vary_headers(response, ('Authorization',))
        return response


class _Counters:
    """The cache every limit counts in: the 'counters' alias, a store that never evicts (COUNTERS_REDIS_URL,
    deploy/compose.yml), or the default cache when none is set (development, the tests). The throttles' histories, the
    day of reading, the sign-in brake, the assistants' shares and the gate's tries live there, apart from the kept
    answers: in one evicting store, a flood of large answers pushed counts out and they started again from zero."""

    def __getattr__(self, name):
        from django.conf import settings
        from django.core.cache import caches
        return getattr(caches['counters' if 'counters' in settings.CACHES else 'default'], name)


counters = _Counters()
