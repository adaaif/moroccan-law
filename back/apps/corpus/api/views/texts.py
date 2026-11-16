"""The views over one text: its answer by its address (or its old id), its outline, what a bill would make of an
article, a link's picture and preview, the index the prerender reads, and the pass past a day's reading."""
from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponseRedirect
from rest_framework.response import Response

from apps.consolidation.models import Change
from apps.consolidation.services import history
from apps.corpus.api.views.answer import (CHUNK, OUTLINE_PER, WINDOW_MAX, Asked, asked_range, outline, text_answer,
                                          text_payload)
from apps.corpus.api.views.base import PublicView, text_ref
from apps.corpus.models import Article, Consolidation, Text, Version, latest_ids
from apps.corpus.services import generation, reading
from apps.corpus.services.addresses import article_path, split_path, text_path
from apps.corpus.services.cards import card_path
from apps.corpus.services.works import text_at
from config import drawing


class Outline(PublicView):
    """GET /api/corpus/outline/<version>/: every article of a version, its anchor, label, number and first words, its
    heading path where it changes. Named with the corpus generation (?g=) it never changes: kept for good. Its first
    words spend the day of reading: one article for every OUTLINE_PER it lists."""

    def get(self, request, version):
        if version >= 2**63:            # past any row's id: a lookup by it overflows SQLite's integers
            raise Http404
        if (stop := reading.refused(request)) is not None:
            return stop

        def build():
            rows = list(Article.objects.filter(version_id=version).order_by('order')
                        .only('id', 'version_id', 'eid', 'label', 'number', 'body', 'heading_path'))
            if not rows and not Version.objects.filter(pk=version).exists():
                raise Http404
            return {'version': version, 'outline': outline(rows)}
        response, listed = generation.counted(['outline', version], build, lambda d: len(d['outline']))
        reading.spend(request, -(-listed // OUTLINE_PER))
        if request.query_params.get('g') and request.query_params['g'] == generation.current('corpus'):
            response['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response


class TextDetail(PublicView):
    """/texts/:id, the address before texts had stable ones: the text's facts and first article, for the app to go on
    to its address (never the text whole: an id is easy to count up)."""

    def get(self, request, pk):
        if (stop := reading.refused(request)) is not None:
            return stop

        def build():
            text = Text.objects.select_related('first_published_in__document').filter(pk=pk).first()
            if text is None:
                raise Http404
            return text_payload(text, window=1)
        response, given = generation.counted(['text', pk], build, lambda d: len(d['articles']))
        reading.spend(request, given)
        return response


class TextAt(PublicView):
    """A text by its address on the site, /ma/loi/60-24, and the article it opens on (…/art_8)."""

    def get(self, request, address):
        uri, eid = split_path(address)
        text, now = text_at(uri)
        if text is None:
            raise Http404
        try:
            on, window, span = asked_range(request.query_params)
        except Asked as wrong:
            return Response({'errors': [{'field': str(wrong), 'code': 'invalid'}]}, status=400)
        if (stop := reading.refused(request)) is not None:
            return stop
        if now != uri:
            # An address it had before 19 Oct 2026, a twin merged into it, or its promulgating dahir (row L1).
            moved = text_path(now) + (f'/{eid}' if eid else '')
            query = request.META.get('QUERY_STRING')
            return HttpResponseRedirect(f'/api/corpus/at{moved}/' + (f'?{query}' if query else ''), status=301)
        if window is None and span is None and not reading.internal(request):
            window = WINDOW_MAX          # a text whole is the server's own (the prerender); a reader's comes a window at a time
        # What the answer carries is counted here, from the articles the view sent, never read back from its JSON.
        response, given = text_answer(text, eid, on, window, span)
        reading.spend(request, given)
        return response


class Proposed(PublicView):
    """GET /api/corpus/proposed/?path=/ma/code/cgi/art_73: what a bill filed in Parliament would make of this article,
    before and after word by word (the finance-bill review, P2). Never law: the page says so."""

    def get(self, request):
        uri, eid = split_path(request.query_params.get('path', ''))
        text, now = text_at(uri)
        if text is None or not eid.startswith('art_'):
            raise Http404
        number = eid.removeprefix('art_')
        # Kept only for an article a bill proposes something for: any other number is answered as it is, never kept.
        from apps.consolidation.services.engine import variants
        proposed = generation.kept(['proposed-numbers', now], lambda: sorted(set(
            Change.objects.filter(text_uri=now, source=Change.Source.BILL).values_list('number', flat=True))))
        if not set(variants(number)) & set(proposed):
            return Response({'path': text_path(now) + f'/{eid}', 'proposals': []})
        return generation.answer(['proposed', now, number],
                                 lambda: {'path': text_path(now) + f'/{eid}', 'proposals': history.proposed(text, number)})


class TextIndex(PublicView):
    """Every text whose words are loaded, with its address, when it last changed and its latest version's article
    anchors: what the prerender writes a page for (?since=ISO datetime for the ones changed since; ?named=1 the shelf's
    and the topics' named texts). Read as (version,
    anchor) pairs, never the articles' words (S2 of the performance audit: 6.3 s and 884 MB before)."""

    def get(self, request):
        if not reading.internal(request):
            # The list of every text was a crawler's map (4 Nov 2026): the prerender's alone, through its tunnel.
            return Response({'errors': [{'field': 'texts', 'code': 'internal'}]}, status=403)
        since = request.query_params.get('since')
        named = request.query_params.get('named') == '1'
        if since:
            # A moment the database can compare, read as the column reads it; «2024-99-99» answered 500.
            try:
                Text._meta.get_field('updated_at').to_python(since)
            except ValidationError:
                return Response({'errors': [{'field': 'since', 'code': 'invalid'}]}, status=400)
        return generation.answer(['texts', since, named], lambda: self.index(since, named))

    @staticmethod
    def index(since: str | None, named: bool = False) -> list[dict]:
        texts = Text.objects.filter(versions__isnull=False).distinct()
        versions = Version.objects.all()
        if named:
            # The shelf's and the topics' named texts, the ones read most: what each deploy prerenders whole (N5).
            from apps.corpus.services import codes
            ids = [t.pk for t in codes.texts_of([k for k, _ in codes.SHELF + codes.MORE]).values() if t is not None]
            texts, versions = texts.filter(pk__in=ids), versions.filter(text_id__in=ids)
        if since:
            texts = texts.filter(updated_at__gte=since)
            versions = versions.filter(text__updated_at__gte=since)
        newest = latest_ids(versions.order_by().values_list('id', 'text_id', 'valid_from', 'consolidation'))
        ids = sorted(newest.values())
        anchors = defaultdict(list)
        for start in range(0, len(ids), CHUNK):
            for version_id, eid in (Article.objects.filter(version_id__in=ids[start:start + CHUNK])
                                    .order_by('version_id', 'order').values_list('version_id', 'eid')):
                anchors[version_id].append(eid)
        return [{'path': text_path(uri), 'updated_at': updated, 'articles': anchors[newest[pk]]}
                for pk, uri, updated in texts.order_by('id').values_list('id', 'akn_uri', 'updated_at')]


class Card(PublicView):
    """The picture a link to a text or an article shows in WhatsApp and the like: ?path=/ma/…/art_8."""

    def get(self, request):
        uri, eid = split_path(request.query_params.get('path', ''))
        text, _ = text_at(uri)
        if text is None:
            raise Http404
        version = text.latest_version()
        article = version.articles.filter(eid=eid).first() if version and eid else None
        if eid and article is None:
            raise Http404

        def picture():
            try:
                path = card_path(text, article, request)
            except drawing.Busy:
                return drawing.busy()
            response = FileResponse(open(path, 'rb'), content_type='image/png')
            response['Cache-Control'] = 'public, max-age=86400'
            return response
        # Never counted against the day of reading: it shows a text's name, or an article's first four lines, and it is
        # asked by whoever shows a link's preview (a messaging app on the sender's phone, a platform's servers), with no
        # cookie, from an address many people share. Counted, the previews of a busy address lost their picture.
        return picture()


class Preview(PublicView):
    """An article (or a text) in a few lines, for a link's preview: ?path=/ma/loi/60-24/art_8."""

    def get(self, request):
        uri, eid = split_path(request.query_params.get('path', ''))
        text, _ = text_at(uri)
        if text is None:
            raise Http404
        version = text.latest_version()
        article = version.articles.filter(eid=eid).first() if version and eid else None
        if eid and article is None:
            raise Http404
        if article is not None and (stop := reading.refused(request)) is not None:
            return stop
        body = article.body if article else ''
        issue = text.first_published_in
        reading.spend(request, 1 if article else 0)
        return Response({'text': text_ref(text), 'label': article.label if article else None,
                         'path': article_path(text.akn_uri, eid) if article else text_path(text.akn_uri),
                         'heading_path': article.heading_path if article else [],
                         'excerpt': body[:420] + ('…' if len(body) > 420 else ''),
                         # Its stamp: the BO issue and page, or the consolidation it comes from.
                         'issue': issue.key if issue else None, 'consolidation': version.consolidation if version else None,
                         'page': article.printed_page if article and version.consolidation == Consolidation.AS_PUBLISHED else None})


class ReadingPass(PublicView):
    """Past a day's reading (apps/corpus/services/reading.py): GET says whether this reader has had their day and the
    check's site key ('' when there is no check), POST {token} gives a reader past their day whom the check passed a day
    of their own, READING_PASSES an address a day."""

    def get(self, request):
        response = Response({'check': settings.TURNSTILE_SITE_KEY if reading.checking() else '',
                             'reached': reading.reached(request)})
        response['Cache-Control'] = 'no-store'
        return response

    def post(self, request):
        token = request.data.get('token') if isinstance(request.data, dict) else None
        if not reading.checking():
            return Response({'errors': [{'field': 'reading', 'code': 'limit'}]}, status=400)
        if not isinstance(token, str) or not token or len(token) > 4096:
            return Response({'errors': [{'field': 'token', 'code': 'invalid'}]}, status=400)
        if (no := reading.no_pass(request)) is not None:
            code, status = no
            response = Response({'errors': [{'field': 'reading', 'code': code}]}, status=status)
            response['Cache-Control'] = 'no-store'
            return response
        if not reading.verify(token, request):
            return Response({'errors': [{'field': 'token', 'code': 'invalid'}]}, status=400)
        response = Response(status=204)
        reading.grant(request, response)
        return response
