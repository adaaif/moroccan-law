from django.urls import path

from apps.seo import views

urlpatterns = [
    path('robots.txt', views.robots),
    path('sitemap.xml', views.sitemap_index),
    path('sitemaps/<str:name>', views.sitemap),
    path('indexnow.txt', views.indexnow_key),
    path('.well-known/security.txt', views.security_txt),
]
