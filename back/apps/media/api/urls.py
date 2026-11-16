from django.urls import path

from apps.media.api.views import ClipAudio, PictureFile

urlpatterns = [
    path('clips/<uuid:pk>/audio/', ClipAudio.as_view(), name='media-clip-audio'),
    path('pictures/<uuid:pk>/<str:size>/', PictureFile.as_view(), name='media-picture'),
]
