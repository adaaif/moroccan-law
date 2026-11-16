"""The authorization server's doors (MC5–MC8). The OAuth endpoints answer as RFC 6749, 7009, 7591, 8414 and 9728 say;
the app's own calls (/api/oauth/…) answer in the site's one error shape."""
from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.exceptions import ParseError, Throttled
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView, exception_handler

from apps.accounts.api.errors import RefusingView
from apps.accounts.services.refusals import Refused
from apps.oauth.models import Client
from apps.oauth.services import clients, connections, flow, tokens
from apps.oauth.services.tokens import OAuthError
from config.malformed import FormParser, JSONParser, MultiPartParser

CONNECT = '/connect'


def _open(response):
    """Metadata and the token endpoint are read by assistants' pages too (the MCP Inspector): any origin, no cookie."""
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, MCP-Protocol-Version'
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response


class Public(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def options(self, request, *args, **kwargs):
        return _open(Response(status=204))

    def finalize_response(self, request, response, *args, **kwargs):
        return _open(super().finalize_response(request, response, *args, **kwargs))

    def get_exception_handler(self):
        return _drf_or_oauth


def _drf_or_oauth(exc, context):
    """OAuth's clients read RFC 6749's errors, not the site's shape: a body that cannot be read (not an object, a NUL) is
    `invalid_request`, and DRF's other refusals answer as DRF writes them."""
    if isinstance(exc, ParseError):
        return _oauth_error(OAuthError('invalid_request', 'The body could not be read.'))
    return exception_handler(exc, context)


def server_metadata() -> dict:
    issuer = settings.OAUTH_ISSUER
    return {
        'issuer': issuer,
        'authorization_endpoint': f'{issuer}/oauth/authorize',
        'token_endpoint': f'{issuer}/oauth/token',
        'registration_endpoint': f'{issuer}/oauth/register',
        'revocation_endpoint': f'{issuer}/oauth/revoke',
        'response_types_supported': ['code'],
        'grant_types_supported': ['authorization_code', 'refresh_token'],
        'code_challenge_methods_supported': ['S256'],
        # Public clients only: Claude uses a metadata document only when «none» is here as well.
        'token_endpoint_auth_methods_supported': ['none'],
        'revocation_endpoint_auth_methods_supported': ['none'],
        'scopes_supported': [flow.SCOPE, 'offline_access'],
        'client_id_metadata_document_supported': True,
        'authorization_response_iss_parameter_supported': True,
        'service_documentation': f'{settings.SITE_URL}/ai',
        'ui_locales_supported': ['ar', 'fr'],
    }


def resource_metadata() -> dict:
    return {
        'resource': settings.MCP_RESOURCE,
        'authorization_servers': [settings.OAUTH_ISSUER],
        # offline_access is the authorization server's, never the resource's (MCP authorization, «Refresh Tokens»).
        'scopes_supported': [flow.SCOPE],
        'bearer_methods_supported': ['header'],
        'resource_name': f'قانون المغرب · {settings.SITE_NAME}',
        'resource_documentation': f'{settings.SITE_URL}/ai',
    }


class ServerMetadata(Public):
    # Read by the assistants' servers for all their users from a few addresses: a wide limit, apart from the token's.
    throttle_scope = 'oauth_metadata'

    def get(self, request):
        return Response(server_metadata())


class ResourceMetadata(Public):
    throttle_scope = 'oauth_metadata'

    def get(self, request):
        return Response(resource_metadata())


class Authorize(Public):
    """GET: the assistant's link. The person goes to /connect, the request's id after «#» (never in a server's log).
    Opened by a person's browser, so its limit counts the person's address; past it, /connect says to wait."""

    throttle_scope = 'oauth_authorize'

    def handle_exception(self, exc):
        if isinstance(exc, Throttled):
            return HttpResponseRedirect(f'{CONNECT}#error=busy')
        return super().handle_exception(exc)

    def get(self, request):
        try:
            raw = flow.authorize(request.query_params)
        except flow.Shown as exc:
            return HttpResponseRedirect(f'{CONNECT}#error={exc.code}')
        except flow.Back as exc:
            return HttpResponseRedirect(exc.url)
        return HttpResponseRedirect(f'{CONNECT}#r={raw}')


def _oauth_error(exc: OAuthError) -> Response:
    response = Response({'error': exc.error, 'error_description': exc.description}, status=exc.status)
    response['Cache-Control'] = 'no-store'
    return response


class Token(Public):
    """POST, form-encoded (RFC 6749 §4.1.3): the code for a pair, or a refresh token for a new pair."""

    parser_classes = [FormParser, MultiPartParser, JSONParser]
    throttle_scope = 'oauth'

    def post(self, request):
        data = request.data
        grant_type = data.get('grant_type', '')
        client_id = data.get('client_id', '')
        try:
            if any(not isinstance(data.get(k), str) for k in data):     # a JSON body's numbers, lists, files
                raise OAuthError('invalid_request', 'Every parameter is a string.')
            if not client_id:
                raise OAuthError('invalid_client', 'client_id is required.', 401)
            # A registration deleted (prune_oauth) is told to register again (RFC 6749 invalid_client, as Claude reads
            # it); a metadata document's client is checked against the code or token it presents.
            registered = Client.objects.filter(client_id=client_id, kind=Client.Kind.DCR).exists()
            if not clients.is_cimd(client_id) and not registered:
                raise OAuthError('invalid_client', 'Unknown client: register again.', 401)
            if grant_type == 'authorization_code':
                answer = tokens.exchange_code(client_id=client_id, code=data.get('code', ''),
                                              redirect_uri=data.get('redirect_uri', ''),
                                              verifier=data.get('code_verifier', ''), resource=data.get('resource', ''))
            elif grant_type == 'refresh_token':
                answer = tokens.refresh(client_id=client_id, token=data.get('refresh_token', ''),
                                        resource=data.get('resource', ''))
            else:
                raise OAuthError('unsupported_grant_type', 'authorization_code or refresh_token.')
        except OAuthError as exc:
            return _oauth_error(exc)
        response = Response(answer)
        response['Cache-Control'] = 'no-store'
        response['Pragma'] = 'no-cache'
        return response


class Revoke(Public):
    """RFC 7009: always 200."""

    parser_classes = [FormParser, MultiPartParser, JSONParser]
    throttle_scope = 'oauth'

    def post(self, request):
        token = request.data.get('token', '')
        tokens.revoke(token if isinstance(token, str) else '')
        return Response(status=200)


class Register(Public):
    """RFC 7591, for the clients that only register (the 2026-07-28 spec deprecates it beside metadata documents)."""

    parser_classes = [JSONParser]
    throttle_scope = 'oauth_register'

    def post(self, request):
        try:
            client = clients.register(request.data)
        except Refused as exc:
            code = 'invalid_redirect_uri' if exc.field == 'redirect_uris' else 'invalid_client_metadata'
            return Response({'error': code, 'error_description': f'{exc.field} is not accepted.'}, status=400)
        return Response({
            'client_id': client.client_id, 'client_id_issued_at': int(client.created_at.timestamp()),
            'client_name': client.name, 'redirect_uris': client.redirect_uris,
            'token_endpoint_auth_method': 'none', 'grant_types': ['authorization_code', 'refresh_token'],
            'response_types': ['code'], 'scope': flow.SCOPE,
        }, status=status.HTTP_201_CREATED)


# The app's own calls from /connect and the account page.

class RequestView(RefusingView):
    """POST {r}: what /connect shows of a waiting request. No account needed to see who asks."""

    permission_classes = [AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        return Response(flow.describe(request.data.get('r', '')))


class ApproveView(RefusingView):
    """POST {r}: the person's yes; answers {redirect} for the page to go to."""

    throttle_scope = 'auth'

    def post(self, request):
        return Response({'redirect': flow.approve(request.data.get('r', ''), request.user)})


class DenyView(RefusingView):
    permission_classes = [AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        return Response({'redirect': flow.deny(request.data.get('r', ''))})


class ConnectionsView(RefusingView):
    def get(self, request):
        return Response(connections.listed(request.user))


class ConnectionView(RefusingView):
    throttle_scope = 'auth'

    def delete(self, request, pk: int):
        connections.end(request.user, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
