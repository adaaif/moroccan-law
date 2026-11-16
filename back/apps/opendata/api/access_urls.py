"""An account's request for access: where it stands, sending it, answering what was asked, asking to change the access
held, ending it."""
from django.urls import path

from apps.opendata.api.access_views import AccessView, AnswerView, ChangeView, EndView, RequestView

urlpatterns = [
    path('', AccessView.as_view(), name='access'),
    path('request/', RequestView.as_view(), name='access-request'),
    path('request/answer/', AnswerView.as_view(), name='access-answer'),
    path('change/', ChangeView.as_view(), name='access-change'),
    path('end/', EndView.as_view(), name='access-end'),
]
