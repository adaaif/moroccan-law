from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.api.errors import JsonOnly, RefusingView, errors_response, serializer_errors_response
from apps.accounts.api.serializers import (
    EmailChangeSerializer,
    GoogleSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfileSerializer,
    RefreshSerializer,
    RegisterSerializer,
    ResetSerializer,
    UserSerializer,
)
from apps.accounts.services import accounts, addresses, brake, codes, google, passwords
from apps.accounts.services.accounts import AccountError
from apps.accounts.services.refusals import Refused
from apps.opendata.throttles import ScopedRate
from config.saved import file_name


class RegisterView(JsonOnly, APIView):
    """Create an account and sign it in: the answer carries the tokens, and whether the code that proves the address
    went (`code_sent`). GET says whether sign-up is open, and writing in the discussion."""

    permission_classes = [AllowAny]
    throttle_scope = 'register'

    def get_throttles(self):
        # The shell asks once a visit what is open (N17 of the read-and-trusted review): never counted against sign-ups.
        return [] if self.request.method == 'GET' else super().get_throttles()

    def get(self, request):
        # And whether assistants read the site without an account (MCP_AUTH): /connect and /ai say so.
        # And Google's client id ('' while it is off): the sign-in and sign-up pages offer «المتابعة بحساب Google».
        # And whether the conversation holds its first hundred posts: a phone's bar gives it a place then (C2).
        from apps.discussion.services import counters
        return Response({'open': settings.REGISTRATION_OPEN, 'discussion': settings.DISCUSSION_OPEN,
                         'talk_alive': settings.DISCUSSION_OPEN and counters.alive(),
                         'mcp_open': settings.MCP_AUTH != 'required', 'google': google.client_id()})

    def post(self, request):
        if not settings.REGISTRATION_OPEN:
            return errors_response([('registration', 'closed')], status.HTTP_403_FORBIDDEN)
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return serializer_errors_response(serializer)
        try:
            user = accounts.register(**serializer.validated_data)
        except AccountError as exc:
            return errors_response(exc.errors)
        # The code that proves the address goes out at once (W1); a letter that fails must not fail the sign-up: the
        # account page says so and sends another.
        try:
            codes.send_proof(user)
            sent = True
        except Refused:
            sent = False
        return Response({'user': UserSerializer(user).data, 'code_sent': sent, **accounts.tokens_for(user)},
                        status=status.HTTP_201_CREATED)


class TokenView(JsonOnly, TokenObtainPairView):
    """Sign in. `username` takes a username or an email address. The password is checked by the authentication
    backend, which holds the brake on wrong passwords (backends.py, brake.py); a refusal is 401 `login.wrong`, or
    `login.typo` with the fixed address when no account holds a misspelt one, and 429 `login.locked` with the minutes
    while the brake holds. With Turnstile set, a held sign-in is 429 `login.check` with the minutes and the `sitekey`:
    the same request with `check`, the token the widget gave, has its password judged."""

    throttle_scope = 'auth'

    def post(self, request, *args, **kwargs):
        checked = LoginSerializer(data=request.data)
        if not checked.is_valid():
            # Said of the login, the field the clients show: `username` is only the token view's name for it.
            return errors_response([('login' if field == 'username' else field, detail.code)
                                    for field, details in checked.errors.items() for detail in details])
        login = checked.validated_data.get('username', '').strip()
        brake.offer(request, request.data.get('check') or '')
        try:
            return super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            if wait := brake.held(request):
                minutes = max(1, -(-wait // 60))
                if brake.checking():
                    return errors_response([('login', 'check', {'minutes': minutes,
                                                                'sitekey': settings.TURNSTILE_SITE_KEY})],
                                           status.HTTP_429_TOO_MANY_REQUESTS)
                return errors_response([('login', 'locked', {'minutes': minutes})], status.HTTP_429_TOO_MANY_REQUESTS)
            fix = addresses.typed_fix(login) if not brake.known(request) and '@' in login else None
            return errors_response([('login', 'typo', {'suggestion': fix}) if fix else ('login', 'wrong')],
                                   status.HTTP_401_UNAUTHORIZED)


class GoogleView(JsonOnly, RefusingView):
    """«المتابعة بحساب Google» (9 Nov 2026, services/google.py): one door for signing in and signing up.

    GET → `{client_id}`, '' while Google is off. POST `{credential, nonce, username?, preferred_language?}`:
    - an account bound to that Google identity, or holding its verified address → signed in (bound the first time):
      200 `{user, access, refresh, created: false}`;
    - nobody yet → 200 `{code: 'google_signup', email}` and no account: the person chooses a username, and the same
      request comes back with it → 201 `{user, access, refresh, created: true}`; 403 `registration.closed` while
      sign-up is;
    - refusals: `google.invalid` 401, `google.off` 503, `google.no_email`, `google.email_unverified`, `google.other`
      409, `login.disabled` 401, `username.username_taken`. Google's ID token lives an hour: the second step reuses it.
    """

    permission_classes = [AllowAny]
    throttle_scope = 'auth'

    def get_throttles(self):
        return [] if self.request.method == 'GET' else super().get_throttles()

    def get(self, request):
        return Response({'client_id': google.client_id()})

    def post(self, request):
        from django.contrib.auth.models import update_last_login

        serializer = GoogleSerializer(data=request.data)
        if not serializer.is_valid():
            return serializer_errors_response(serializer)
        data = serializer.validated_data
        claims = google.verify(data['credential'], nonce=data['nonce'])
        user, created = google.find(claims), False
        if user is None:
            if not settings.REGISTRATION_OPEN:
                return errors_response([('registration', 'closed')], status.HTTP_403_FORBIDDEN)
            if not data.get('username'):
                return Response({'code': 'google_signup', 'email': google.address(claims)})
            user, created = google.create(claims, username=data['username'],
                                          preferred_language=data['preferred_language'])
        else:
            if not user.is_active:
                raise Refused('login', 'disabled', status.HTTP_401_UNAUTHORIZED)
            user = google.link(user, claims)
        update_last_login(None, user)
        return Response({'user': UserSerializer(user).data, 'created': created, **accounts.tokens_for(user)},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class RefreshThrottle(ScopedRate):
    """A refresh counted by the account its token names, not by the address. Thousands of phones can sit behind one
    carrier address, each refreshing every half hour; in the sign-in's bucket, one person's wrong sign-ins there made
    everyone else's refresh fail. A token that does not decode counts its address, as every limit counts one
    (apps/opendata/throttles.py)."""

    def get_cache_key(self, request, view):
        from rest_framework_simplejwt.exceptions import TokenBackendError
        from rest_framework_simplejwt.settings import api_settings as jwt_settings
        from rest_framework_simplejwt.state import token_backend

        data = request.data
        token = data.get('refresh') if isinstance(data, dict) else None
        try:
            account = token_backend.decode(str(token), verify=True).get(jwt_settings.USER_ID_CLAIM) if token else None
        except TokenBackendError:
            account = None
        ident = f'account-{account}' if account else self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class TokenRefresh(JsonOnly, TokenRefreshView):
    serializer_class = RefreshSerializer
    throttle_classes = [RefreshThrottle]
    throttle_scope = 'refresh'

    def post(self, request, *args, **kwargs):
        # A token whose account was deleted is a dead token: it raised, and the phone got a 500 instead of being signed
        # out (RD17 of the readers review, seen once on 9 Nov 2026).
        try:
            return super().post(request, *args, **kwargs)
        except ObjectDoesNotExist as exc:
            raise InvalidToken() from exc


class LogoutView(JsonOnly, APIView):
    """Takes the refresh token alone, so a page whose access token expired can still sign out."""

    permission_classes = [AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return serializer_errors_response(serializer)
        try:
            accounts.logout(serializer.validated_data['refresh'])
        except AccountError as exc:
            return errors_response(exc.errors)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return serializer_errors_response(serializer)
        try:
            user = accounts.update_profile(request.user, **serializer.validated_data)
        except AccountError as exc:
            return errors_response(exc.errors)
        return Response(UserSerializer(user).data)


class EmailCodeView(RefusingView):
    """POST: a six-digit code to the account's address, which proves it (D3)."""

    throttle_scope = 'codes'

    def post(self, request):
        codes.send_proof(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmailProveView(RefusingView):
    """POST {code}."""

    throttle_scope = 'codes'

    def post(self, request):
        codes.prove(request.user, request.data.get('code'))
        return Response(UserSerializer(request.user).data)


class PasswordView(RefusingView):
    """POST {password, new_password}: a new password. The other devices are signed out; this one gets a fresh pair."""

    throttle_scope = 'password'

    def post(self, request):
        return Response(passwords.change(request.user, password=request.data.get('password'),
                                         new_password=request.data.get('new_password'), ip=brake.address(request)))


class EmailView(RefusingView):
    """POST {email, password, email_confirmed?}: a new address, unproven until the code sent to it comes back."""

    throttle_scope = 'password'

    def post(self, request):
        user = request.user
        checked = EmailChangeSerializer(data=request.data)
        if not checked.is_valid():
            return serializer_errors_response(checked)
        email = checked.validated_data.get('email', '')
        if not email.strip():
            raise Refused('email', 'required')
        # The address first: it needs no password to be judged, and a typo should not cost a try.
        confirmed = request.data.get('email_confirmed') is True
        verdict = addresses.check(email, confirmed=confirmed)
        if verdict.code:
            raise AccountError([accounts.address_error(verdict)])
        passwords.checked(user, request.data.get('password'), brake.address(request))
        sent = accounts.change_email(user, email=email, confirmed=confirmed)
        return Response({'user': UserSerializer(user).data, 'code_sent': sent})


class ResetView(JsonOnly, RefusingView):
    """POST {login}: a username or an address; a reset link to the account's address. Answers {to}, the address masked,
    when the login was one; {} for a username."""

    permission_classes = [AllowAny]
    throttle_scope = 'reset'

    def post(self, request):
        checked = ResetSerializer(data=request.data)
        if not checked.is_valid():
            return serializer_errors_response(checked)
        return Response(passwords.request_reset(checked.validated_data.get('login')))


class ResetCheckView(JsonOnly, RefusingView):
    """POST {uid, token}: is the link still good? Answers {username}, or 400 `link.dead`."""

    permission_classes = [AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        return Response(passwords.check_reset(request.data.get('uid'), request.data.get('token')))


class ResetConfirmView(JsonOnly, RefusingView):
    """POST {uid, token, password}: the new password; signs in (answers {user, access, refresh})."""

    permission_classes = [AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        user, tokens = passwords.confirm_reset(request.data.get('uid'), request.data.get('token'),
                                               request.data.get('password'))
        return Response({'user': UserSerializer(user).data, **tokens})


class ExportView(RefusingView):
    """GET: everything the site keeps about this account, as JSON (law 09-08)."""

    def get(self, request):
        from apps.discussion.services import leaving

        response = Response(leaving.export(request.user))
        response['Content-Disposition'] = f'attachment; filename="{file_name(f"{request.user.username}.json")}"'
        return response


class DeleteAccountView(RefusingView):
    """POST {password}: the account deleted; its written words stay as «حساب محذوف», its voices and pictures go. The
    password counts with the brake."""

    throttle_scope = 'auth'

    def post(self, request):
        from apps.discussion.services import leaving

        passwords.checked(request.user, request.data.get('password'), brake.address(request))
        leaving.delete_account(request.user, request.data.get('password', ''))
        return Response(status=status.HTTP_204_NO_CONTENT)
