from django.urls import path

from apps.analytics.api import views

urlpatterns = [
    path('', views.MeasureView.as_view(), name='measure'),
]
