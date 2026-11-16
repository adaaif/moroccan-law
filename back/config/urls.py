from django.contrib import admin
from django.urls import include, path, re_path

from apps.corpus.api.views import issue_page, law_page, search_page, text_by_id, words_page

urlpatterns = [
    path('admin/', admin.site.urls),
    path('gate/', include('apps.gate.urls')),
    path('api/auth/', include('apps.accounts.api.urls')),
    path('api/oauth/', include('apps.oauth.api.urls')),
    # The assistants' sign-in at the site's root: its metadata where clients look, and /oauth/ (apps.oauth).
    path('', include('apps.oauth.urls')),
    path('api/corpus/', include('apps.corpus.api.urls')),
    path('api/sources/', include('apps.sources.api.urls')),
    path('api/budget/', include('apps.budget.api.urls')),
    path('api/search/', include('apps.search.api.urls')),
    path('api/quality/', include('apps.quality.api.urls')),
    path('api/open/', include('apps.opendata.urls')),
    # Access on request: an account's request, its keys and their use; the versioned API a key opens.
    path('api/access/', include('apps.opendata.api.urls')),
    path('api/v1/', include('apps.opendata.v1.urls')),
    path('api/discussion/', include('apps.discussion.api.urls')),
    path('api/explain/', include('apps.explain.api.urls')),
    path('api/follows/', include('apps.follows.api.urls')),
    path('api/topics/', include('apps.topics.api.urls')),
    path('api/blog/', include('apps.blog.urls')),
    path('api/places/', include('apps.places.api.urls')),
    path('api/media/', include('apps.media.api.urls')),
    path('api/measure/', include('apps.analytics.api.urls')),
    # A law's address with its own head, when nginx has no prerendered file for it (N5 of the read-and-trusted review).
    re_path(r'^ma/', law_page),
    re_path(r'^search$', search_page),
    # Their own heads and words (IX8 of the search-engines review); the old /texts/<id> said by the server (IX3).
    re_path(r'^bo/(?P<edition>[a-z_]+)/(?P<key>[0-9]+(?:-[a-z]+)?)$', issue_page),
    path('words', words_page),
    path('words/<slug:slug>', words_page),
    path('texts/<int:pk>', text_by_id),
    # robots.txt, the sitemaps and IndexNow's key (apps.seo).
    path('', include('apps.seo.urls')),
]
