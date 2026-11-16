"""At the site's root: the metadata where clients look for it, and the OAuth endpoints (nginx sends /.well-known/ and
/oauth/ to Django)."""
from django.urls import path

from apps.oauth.api.views import Authorize, Register, ResourceMetadata, Revoke, ServerMetadata, Token

urlpatterns = [
    path('.well-known/oauth-authorization-server', ServerMetadata.as_view(), name='oauth-server-metadata'),
    path('.well-known/oauth-protected-resource', ResourceMetadata.as_view(), name='oauth-resource-metadata'),
    path('.well-known/oauth-protected-resource/mcp', ResourceMetadata.as_view(), name='oauth-resource-metadata-mcp'),
    path('oauth/authorize', Authorize.as_view(), name='oauth-authorize'),
    path('oauth/token', Token.as_view(), name='oauth-token'),
    path('oauth/revoke', Revoke.as_view(), name='oauth-revoke'),
    path('oauth/register', Register.as_view(), name='oauth-register'),
]
