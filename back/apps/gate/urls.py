from django.urls import path

from apps.gate import views

urlpatterns = [
    path('', views.page, name='gate'),
    path('check/', views.check, name='gate-check'),
]
