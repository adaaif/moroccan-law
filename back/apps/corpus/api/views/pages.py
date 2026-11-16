"""The site's pages Django answers with their own heads, the app taking over in the browser: a law, a search, an
issue, the words; and a text's old address said by the server."""
from django.http import HttpResponsePermanentRedirect

from apps.corpus.models import Text
from apps.corpus.services.addresses import text_path


def law_page(request):
    """GET /ma/…: the app's page with that law's own head (N5 of the read-and-trusted review) and, since
    the search-engines review, its words drawn by the app's components (IX1), for the addresses nginx has no prerendered file for; a 404
    for an address that leads nowhere (IX2), a 301 from an old address (IX3). The app takes over in the browser."""
    from apps.corpus.services import heads
    return heads.law(request)


def search_page(request):
    """GET /search?q=…: the app's page with the search's own head (HM5 of the hard-moment review): the question as
    the title, what its first door says, that door's card; the app takes over in the browser."""
    from django.http import HttpResponse

    from apps.corpus.services import heads
    response = HttpResponse(heads.search_page(request.GET.get('q', '')), content_type='text/html; charset=utf-8')
    response['Cache-Control'] = 'no-cache'
    return response


def issue_page(request, edition, key):
    """GET /bo/<edition>/<key>: a Bulletin issue's page with its own head and its list of texts (IX8 of
    the search-engines review)."""
    from apps.corpus.services import heads
    return heads.issue(request, edition, key)


def words_page(request, slug=''):
    """GET /words, /words/<slug>: the words' pages with their own heads (IX8 of the search-engines review)."""
    from apps.corpus.services import heads
    return heads.words(request, slug)


def text_by_id(request, pk):
    """GET /texts/<id>: the text's own address, said by the server (IX3 of the search-engines review; the app's redirect was
    a page of its own to a crawler)."""
    from apps.corpus.services import heads
    found = Text.objects.filter(pk=pk).values_list('akn_uri', flat=True).first()
    if found is None:
        return heads._missing()
    return HttpResponsePermanentRedirect(text_path(found))
