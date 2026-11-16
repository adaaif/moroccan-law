from django.urls import path

from apps.search.api.views import Event, FindIn, Opened, People, Resolve, Search, Suggest

urlpatterns = [
    path('', Search.as_view(), name='search'),
    path('people/', People.as_view(), name='search-people'),
    path('suggest/', Suggest.as_view(), name='search-suggest'),
    path('in/', FindIn.as_view(), name='search-in'),
    path('resolve/', Resolve.as_view(), name='search-resolve'),
    path('opened/', Opened.as_view(), name='search-opened'),
    path('event/', Event.as_view(), name='search-event'),
]
