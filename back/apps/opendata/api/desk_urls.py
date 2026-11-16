"""The access desk, for a superuser: what waits, every request and access, their use, the editions, the log."""
from django.urls import path

from apps.opendata.api import desk_views as v

urlpatterns = [
    path('', v.Home.as_view(), name='access-desk'),
    path('requests/', v.Requests.as_view(), name='access-desk-requests'),
    path('requests/<int:pk>/', v.RequestSheet.as_view(), name='access-desk-request'),
    path('requests/<int:pk>/preview/', v.Preview.as_view(), name='access-desk-preview'),
    path('requests/<int:pk>/accept/', v.Accept.as_view(), name='access-desk-accept'),
    path('requests/<int:pk>/ask/', v.Ask.as_view(), name='access-desk-ask'),
    path('requests/<int:pk>/decline/', v.Decline.as_view(), name='access-desk-decline'),
    path('accesses/', v.Accesses.as_view(), name='access-desk-accesses'),
    path('accesses/<int:pk>/', v.AccessSheet.as_view(), name='access-desk-access'),
    path('accesses/<int:pk>/change/', v.Change.as_view(), name='access-desk-change'),
    path('accesses/<int:pk>/renew/', v.Renew.as_view(), name='access-desk-renew'),
    path('accesses/<int:pk>/end/', v.End.as_view(), name='access-desk-end'),
    path('keys/<int:pk>/end/', v.KeyEnd.as_view(), name='access-desk-key-end'),
    path('use/', v.Use.as_view(), name='access-desk-use'),
    path('editions/', v.Editions.as_view(), name='access-desk-editions'),
    path('log/', v.Log.as_view(), name='access-desk-log'),
]
