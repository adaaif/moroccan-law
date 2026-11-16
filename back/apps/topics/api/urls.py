from django.urls import path

from apps.topics.api.views import Calendar, Card, Cites, HelpedView, Moments, Places, Review, Topic, TopicPage, Topics, UseView

urlpatterns = [
    path('', Topics.as_view(), name='topics'),
    path('helped/', HelpedView.as_view(), name='topics-helped'),
    path('calendar/', Calendar.as_view(), name='topics-calendar'),
    path('moments/', Moments.as_view(), name='topics-moments'),
    path('cites/', Cites.as_view(), name='topics-cites'),
    path('use/', UseView.as_view(), name='topics-use'),
    path('land/places/', Places.as_view(), name='land-places'),
    path('<slug:slug>/', Topic.as_view(), name='topic'),
    path('<slug:slug>/review/', Review.as_view(), name='topic-review'),
    path('<slug:slug>/card/', Card.as_view(), name='topic-card'),
    path('<slug:slug>/<str:kind>/<slug:key>/', TopicPage.as_view(), name='topic-page'),
]
