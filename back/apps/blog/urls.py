from django.urls import path

from apps.blog.views import Card, Post, Posts, PostYears

urlpatterns = [
    path('', Posts.as_view(), name='blog-posts'),
    path('<slug:slug>/', Post.as_view(), name='blog-post'),
    path('<slug:slug>/card/', Card.as_view(), name='blog-card'),
    path('<slug:slug>/years.csv', PostYears.as_view(), name='blog-post-years'),
]
