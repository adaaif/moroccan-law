from django.urls import path

from apps.places.api.views import Mentions, PlaceView, Places

urlpatterns = [
    path('', Places.as_view(), name='places'),
    path('<slug:slug>/', PlaceView.as_view(), name='place'),
    path('<slug:slug>/mentions/', Mentions.as_view(), name='place-mentions'),
]
