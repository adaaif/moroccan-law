from django.urls import path

from apps.sources.api.views import DocumentFile, PageDetail, PageImage, PageRegion

urlpatterns = [
    path('documents/<int:document_id>/file/', DocumentFile.as_view(), name='sources-document-file'),
    path('documents/<int:document_id>/pages/<int:index>/', PageDetail.as_view(), name='sources-page'),
    path('documents/<int:document_id>/pages/<int:index>/image/', PageImage.as_view(), name='sources-page-image'),
    path('documents/<int:document_id>/pages/<int:index>/region/', PageRegion.as_view(), name='sources-page-region'),
]
