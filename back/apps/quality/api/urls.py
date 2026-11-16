from django.urls import path

from apps.quality.api.views import (Corrections, Decide, NextWord, ReportCreate, Strip, TimingCreate, WordAnswer,
                                     Words)

urlpatterns = [
    path('reports/', ReportCreate.as_view(), name='quality-report'),
    path('timing/', TimingCreate.as_view(), name='quality-timing'),
    path('corrections/', Corrections.as_view(), name='quality-corrections'),
    path('corrections/<int:pk>/<str:verb>/', Decide.as_view(), name='quality-correction-decide'),
    path('words/', Words.as_view(), name='quality-words'),
    path('words/next/', NextWord.as_view(), name='quality-word-next'),
    path('words/<int:pk>/', WordAnswer.as_view(), name='quality-word-answer'),
    path('words/<int:pk>/strip/', Strip.as_view(), name='quality-word-strip'),
]
