"""/api/access/: what a signed-in account does about its access. Its request (access_urls) and its keys with
their use (key_urls); and, for a superuser, the desk where requests are answered and accesses run (desk_urls)."""
from django.urls import include, path

urlpatterns = [
    path('keys/', include('apps.opendata.api.key_urls')),
    path('desk/', include('apps.opendata.api.desk_urls')),
    path('', include('apps.opendata.api.access_urls')),
]
