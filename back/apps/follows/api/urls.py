from django.urls import path

from apps.follows.api import views as v

urlpatterns = [
    path('', v.Follows.as_view(), name='follows'),
    path('news/', v.News.as_view(), name='follows-news'),
]
