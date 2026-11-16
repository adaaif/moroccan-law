from django.urls import path

from apps.budget.api.views import FinanceLawDetail, FinanceLawList

urlpatterns = [
    path('laws/', FinanceLawList.as_view(), name='budget-laws'),
    path('laws/<int:year>/', FinanceLawDetail.as_view(), name='budget-law'),
]
