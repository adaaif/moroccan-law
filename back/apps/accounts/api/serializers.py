from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password

from apps.accounts.models import AddressForm, Language, reserved_username

# Letters (Arabic too), digits, «.», «-» and «_». No «@»: a sign-in holding
# one is read as an email address.
USERNAME_PATTERN = r'^[\w.-]+\Z'
# The longest address there can be (RFC 5321), and the column's length. A login is a username or an address, so it is
# never longer either. What is longer is refused before anything reads it: the typo check runs an edit distance over it.
ADDRESS_MAX = 254


class LoginSerializer(serializers.Serializer):
    """The sign-in's login (`username`, as the token view names it): only its length and its characters are judged
    here; an empty or missing one is the token view's to refuse, as before."""
    username = serializers.CharField(max_length=ADDRESS_MAX, required=False, allow_blank=True)


class ResetSerializer(serializers.Serializer):
    login = serializers.CharField(max_length=ADDRESS_MAX, required=False, allow_blank=True)


class EmailChangeSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=ADDRESS_MAX, required=False, allow_blank=True, trim_whitespace=False)


def _chosen_username(value: str) -> str:
    """A name a person chooses, never one the code gives its own accounts (models.RESERVED_PREFIXES)."""
    if reserved_username(value):
        raise serializers.ValidationError('reserved', code='reserved')
    return value


class RegisterSerializer(serializers.Serializer):
    username = serializers.RegexField(USERNAME_PATTERN, min_length=3, max_length=30, validators=[_chosen_username])
    # Checked by the service (addresses.check): it cleans what an Arabic keyboard slips in before judging the format.
    email = serializers.CharField(max_length=254)
    # The person saw the suggested fix of a misspelt provider and kept the address as typed.
    email_confirmed = serializers.BooleanField(required=False, default=False)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    display_name = serializers.CharField(max_length=40, required=False, allow_blank=True,
                                         default='')
    preferred_language = serializers.ChoiceField(choices=Language.choices, required=False,
                                                 default=Language.ARABIC)


class GoogleSerializer(serializers.Serializer):
    """«المتابعة بحساب Google»: `credential` is the ID token Google just handed the page; everything about the person is
    read from ITS signed claims, never from this body. `nonce` is the one the web put in Google's link. `username` comes
    on the second step of a sign-up, chosen by the person."""
    credential = serializers.CharField(max_length=4096)
    nonce = serializers.CharField(max_length=128, required=False, allow_blank=True, default='')
    username = serializers.RegexField(USERNAME_PATTERN, min_length=3, max_length=30, required=False,
                                      validators=[_chosen_username])
    preferred_language = serializers.ChoiceField(choices=Language.choices, required=False, default=Language.ARABIC)


class ProfileSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=40, required=False, allow_blank=True)
    preferred_language = serializers.ChoiceField(choices=Language.choices, required=False)
    address_form = serializers.ChoiceField(choices=AddressForm.choices, required=False, allow_blank=True)
    email_notices = serializers.BooleanField(required=False)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    email_proven = serializers.SerializerMethodField()
    # Bound to a Google account (services/google.py), and whether it has a password: an account Google opened has
    # none until «نسيت كلمة السر» sets one, so the account page offers that instead of a change.
    google = serializers.SerializerMethodField()
    has_password = serializers.SerializerMethodField()
    # Whether the account may open the access desk (/data/desk): the web shows its link to nobody else. The desk's own
    # doors check it again on every call.
    desk = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'display_name', 'preferred_language',
                  'date_joined', 'email_proven', 'address_form', 'email_notices', 'google', 'has_password', 'desk']
        read_only_fields = fields

    def get_email_proven(self, user) -> bool:
        return bool(user.email_proven_at)

    def get_google(self, user) -> bool:
        return bool(user.google_sub)

    def get_has_password(self, user) -> bool:
        return user.has_usable_password()

    def get_desk(self, user) -> bool:
        return bool(user.is_active and user.is_superuser)


class PasswordBoundRefreshToken(RefreshToken):
    """A refresh token that dies with the password it was made under. simplejwt checks CHECK_REVOKE_TOKEN's mark on
    access tokens only: a refresh token from before a new password would go on making access tokens the API refuses,
    and the app would never learn the session is over. One query, the account's password."""

    def verify(self, *args, **kwargs) -> None:
        super().verify(*args, **kwargs)
        password = (get_user_model().objects.filter(pk=self.payload.get(jwt_settings.USER_ID_CLAIM))
                    .values_list('password', flat=True).first())
        # A deleted account is the refresh view's to refuse.
        if password is not None and self.payload.get(jwt_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(password):
            raise TokenError('password changed')


class RefreshSerializer(TokenRefreshSerializer):
    token_class = PasswordBoundRefreshToken
