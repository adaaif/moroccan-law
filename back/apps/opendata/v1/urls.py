"""/api/v1/: the versioned API a key opens (views.py), described in openapi.yaml.

v1 only grows. Inside v1 a field is added, never renamed or removed, and a read keeps its address and its meaning. A
read that will go is announced 90 days ahead: on each of its answers by the Deprecation and Sunset headers
(deprecated.py) and in a letter to the holders of the keys that used it. A change that cannot be made by adding is v2,
beside v1, never in place of it."""
from django.urls import path

from apps.opendata.v1 import views

urlpatterns = [
    path('search', views.Search.as_view(), name='v1-search'),
    path('texts/<path:path>', views.Texts.as_view(), name='v1-text'),
    path('articles/<path:path>', views.Articles.as_view(), name='v1-articles'),
    path('references', views.References.as_view(), name='v1-references'),
    path('bulletin/', views.Bulletin.as_view(), name='v1-bulletin-latest'),
    path('bulletin/<str:issue>', views.Bulletin.as_view(), name='v1-bulletin'),
    path('changes', views.Changes.as_view(), name='v1-changes'),
    path('openapi.yaml', views.openapi, name='v1-openapi'),
]
