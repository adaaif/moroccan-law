"""GET /api/blog/ — the posts; GET /api/blog/<slug>/ — a post's meta and its counted figures; GET
/api/blog/<slug>/years.csv — its yearly table, for whoever wants to count again. Files read from disk, no query."""
from django.http import FileResponse, Http404, HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.blog.services import posts
from apps.corpus.services import generation
from apps.opendata.throttles import PublicRate
from config.saved import file_name

NOT_FOUND = {'errors': [{'field': 'slug', 'code': 'not_found'}]}


class BlogView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicRate]


class Posts(BlogView):
    def get(self, request):
        # Kept rendered for every worker until a post's file changes (RD15 of the readers review): each new worker read
        # every post's meta again, a slow read, and the home asks this list.
        response = generation.answer(['blog', 'posts', generation.files(*(posts.ROOT / s / 'meta.yaml' for s in posts.slugs()))],
                                     lambda: {'posts': posts.listing()})
        response['Cache-Control'] = 'public, max-age=3600'
        return response


class Post(BlogView):
    def get(self, request, slug):
        found = posts.post(slug)
        if found is None:
            return Response(NOT_FOUND, status=404)
        response = Response(found)
        response['Cache-Control'] = 'public, max-age=3600'
        return response


class PostYears(BlogView):
    def get(self, request, slug):
        body = posts.years_csv(slug)
        if body is None:
            return Response(NOT_FOUND, status=404)
        response = HttpResponse(body, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{file_name(f"{slug}-years.csv")}"'
        response['Cache-Control'] = 'public, max-age=3600'
        return response


class Card(BlogView):
    """The picture a link to a post shows (HM5 of the hard-moment review: a post shared on WhatsApp previewed as
    the bare site): its title and lead on the paper, drawn as a topic's card is."""

    def get(self, request, slug):
        from apps.topics.services.cards import drawn
        found = posts.post(slug)
        if found is None:
            raise Http404
        path = drawn({'slug': 'blog', 'name': found['title']['ar'], 'lead': found['lead']['ar'], 'doors': ['قانون بالأرقام']})
        response = FileResponse(open(path, 'rb'), content_type='image/png')
        response['Cache-Control'] = 'public, max-age=86400'
        return response
