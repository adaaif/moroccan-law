from django.urls import path

from apps.accounts.api.views import (DeleteAccountView, EmailCodeView, EmailProveView, EmailView, ExportView, GoogleView,
                                     LogoutView, MeView, PasswordView, RegisterView, ResetCheckView, ResetConfirmView,
                                     ResetView, TokenRefresh, TokenView)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('token/', TokenView.as_view(), name='auth-token'),
    path('google/', GoogleView.as_view(), name='auth-google'),
    path('token/refresh/', TokenRefresh.as_view(), name='auth-token-refresh'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('me/export/', ExportView.as_view(), name='auth-export'),
    path('me/delete/', DeleteAccountView.as_view(), name='auth-delete'),
    path('email/', EmailView.as_view(), name='auth-email'),
    path('email/code/', EmailCodeView.as_view(), name='auth-email-code'),
    path('email/prove/', EmailProveView.as_view(), name='auth-email-prove'),
    path('password/', PasswordView.as_view(), name='auth-password'),
    path('password/reset/', ResetView.as_view(), name='auth-password-reset'),
    path('password/reset/check/', ResetCheckView.as_view(), name='auth-password-reset-check'),
    path('password/reset/confirm/', ResetConfirmView.as_view(), name='auth-password-reset-confirm'),
]
