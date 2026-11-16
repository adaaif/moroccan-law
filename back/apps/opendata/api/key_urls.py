"""An access's keys and their use."""
from django.urls import path

from apps.opendata.api.key_views import Key, Keys

urlpatterns = [
    path('', Keys.as_view(), name='access-keys'),
    path('<int:pk>/', Key.as_view(), name='access-key'),
]
