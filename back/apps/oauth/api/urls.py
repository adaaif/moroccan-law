from django.urls import path

from apps.oauth.api.views import ApproveView, ConnectionsView, ConnectionView, DenyView, RequestView

urlpatterns = [
    path('request/', RequestView.as_view(), name='oauth-request'),
    path('approve/', ApproveView.as_view(), name='oauth-approve'),
    path('deny/', DenyView.as_view(), name='oauth-deny'),
    path('connections/', ConnectionsView.as_view(), name='oauth-connections'),
    path('connections/<int:pk>/', ConnectionView.as_view(), name='oauth-connection'),
]
