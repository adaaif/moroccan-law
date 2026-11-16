from django.urls import path

from apps.opendata.views import About, EditionFile, Manifest, Ticket

urlpatterns = [
    path('', Manifest.as_view(), name='open-manifest'),
    path('about/', About.as_view(), name='open-about'),
    path('ticket/', Ticket.as_view(), name='open-ticket'),
    # `latest` or an edition's date (services/editions.py `find`), then one of its files.
    path('<str:edition>/<str:name>', EditionFile.as_view(), name='open-file'),
]
