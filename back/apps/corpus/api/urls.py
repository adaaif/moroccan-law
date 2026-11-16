from django.urls import path

from apps.corpus.api.export import Export
from apps.corpus.api.views import (Card, Proposed, ConstitutionAt, ConstitutionHistory, ConstitutionLineage, Find, IssueDetail, IssueList, IssueMap, IssueQuality, Library, LibraryCard, Outline, Preview, ReadingPass, Shelf, Situations, TextAt, TextDetail, Year,
                                   TextIndex)

urlpatterns = [
    path('issues/', IssueList.as_view(), name='corpus-issues'),
    path('issues/map/', IssueMap.as_view(), name='corpus-issue-map'),
    path('issues/<str:edition>/<str:key>/', IssueDetail.as_view(), name='corpus-issue'),
    path('issues/<str:edition>/<str:key>/quality/', IssueQuality.as_view(), name='corpus-issue-quality'),
    path('texts/', TextIndex.as_view(), name='corpus-texts'),
    path('texts/<int:pk>/', TextDetail.as_view(), name='corpus-text'),
    path('at/<path:address>/', TextAt.as_view(), name='corpus-text-at'),
    path('outline/<int:version>/', Outline.as_view(), name='corpus-outline'),
    path('proposed/', Proposed.as_view(), name='corpus-proposed'),
    path('preview/', Preview.as_view(), name='corpus-preview'),
    path('card/', Card.as_view(), name='corpus-card'),
    path('export/', Export.as_view(), name='corpus-export'),
    path('reading/', ReadingPass.as_view(), name='corpus-reading'),
    path('shelf/', Shelf.as_view(), name='corpus-shelf'),
    path('find/', Find.as_view(), name='corpus-find'),
    path('years/<int:year>/', Year.as_view(), name='corpus-year'),
    path('library/', Library.as_view(), name='corpus-library'),
    path('library/card/', LibraryCard.as_view(), name='corpus-library-card'),
    path('constitution/', ConstitutionAt.as_view(), name='corpus-constitution'),
    path('constitution/history/', ConstitutionHistory.as_view(), name='corpus-constitution-history'),
    path('constitution/lineage/', ConstitutionLineage.as_view(), name='corpus-constitution-lineage'),
    path('situations/', Situations.as_view(), name='corpus-situations'),
]
