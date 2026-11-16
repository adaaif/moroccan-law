from django.urls import path

from apps.explain.api import views as v

urlpatterns = [
    path('text/', v.TextBundle.as_view(), name='explain-text'),
    path('at/', v.At.as_view(), name='explain-at'),
    path('save/', v.Save.as_view(), name='explain-save'),
    path('check/', v.Check.as_view(), name='explain-check'),
    path('report/', v.Report.as_view(), name='explain-report'),
    path('act/', v.Act.as_view(), name='explain-act'),
    path('waiting/', v.Waiting.as_view(), name='explain-waiting'),
    path('helpful/', v.Helpful.as_view(), name='explain-helpful'),
    path('new/', v.New.as_view(), name='explain-new'),
    path('week/', v.Week.as_view(), name='explain-week'),
    path('card/', v.Card.as_view(), name='explain-card'),
    path('words/', v.Words.as_view(), name='explain-words'),
    path('words/<slug:slug>/', v.Word.as_view(), name='explain-word'),
]
