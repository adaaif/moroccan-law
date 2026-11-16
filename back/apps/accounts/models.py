from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class Language(models.TextChoices):
    ARABIC = 'ar', 'العربية'
    FRENCH = 'fr', 'Français'


class AddressForm(models.TextChoices):
    """How Arabic addresses a person: a word about them («كتبت» / «كتب») takes it. Unsaid is
    the masculine, Arabic's general form."""
    UNSAID = '', 'Not said'
    MASCULINE = 'm', 'Masculine'
    FEMININE = 'f', 'Feminine'


# Names the code gives accounts of its own: the development's demo people («demo-…», seed_demo_talk), the load test's
# («load-…», seed_load_test) and a deleted account's emptied row («deleted-<id>», discussion/services/leaving.py).
# Nobody may choose one: a demo name would pass for the site's own, and a «deleted-<id>» taken first would stop that
# account's deletion. The development's addresses beside them: those accounts are never people.
RESERVED_PREFIXES = ('demo-', 'load-', 'deleted-')
RESERVED_DOMAINS = ('@demo.law.invalid', '@load.law.invalid')


def reserved_username(username: str) -> bool:
    return (username or '').strip().lower().startswith(RESERVED_PREFIXES)


def reserved_accounts() -> models.Q:
    """The accounts the code made for itself (`RESERVED_PREFIXES`, `RESERVED_DOMAINS`)."""
    q = models.Q()
    for prefix in RESERVED_PREFIXES:
        q |= models.Q(username__istartswith=prefix)
    for domain in RESERVED_DOMAINS:
        q |= models.Q(email__iendswith=domain)
    return q


class User(AbstractUser):
    """An account. Signing in takes the username or the email address."""

    first_name = None
    last_name = None
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=40, blank=True, default='', db_default='')
    preferred_language = models.CharField(
        max_length=2,
        choices=Language.choices,
        default=Language.ARABIC,
        db_default=Language.ARABIC,
    )

    # The discussion (D3): writing needs a proven address, by a six-digit code sent to it.
    email_proven_at = models.DateTimeField(null=True, blank=True)
    # When the account agreed that a model reads its posts before they are published, abroad (law 09-08, art. 44).
    check_consent_at = models.DateTimeField(null=True, blank=True)
    address_form = models.CharField(max_length=1, choices=AddressForm.choices, blank=True, default='',
                                    db_default='')
    # An email when someone answers in a discussion this person follows.
    email_notices = models.BooleanField(default=True, db_default=True)
    # The account was deleted: its row stays, emptied, so its written words can say «حساب محذوف».
    deleted_at = models.DateTimeField(null=True, blank=True)
    # «المتابعة بحساب Google» (9 Nov 2026, services/google.py): Google's number for the person (`sub`), which never
    # changes when their address does. Their address and this, nothing else of Google's is kept.
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True)

    REQUIRED_FIELDS = ['email']

    class Meta:
        db_table = 'users'
        constraints = [
            # A name or an address belongs to one person whatever its letter case.
            models.UniqueConstraint(Lower('username'), name='users_username_ci_unique'),
            models.UniqueConstraint(Lower('email'), name='users_email_ci_unique'),
        ]

    def __str__(self):
        return self.username

    def clean(self):
        """A rename in the admin's form may not take a reserved name; an account that already holds one keeps it."""
        super().clean()
        if reserved_username(self.username) and not (
                self.pk and type(self).objects.filter(pk=self.pk, username=self.username).exists()):
            from django.core.exceptions import ValidationError
            raise ValidationError({'username': ValidationError('This name is kept for accounts the code makes.',
                                                               code='reserved')})

    @property
    def shown_name(self):
        return self.display_name or self.username

    def get_full_name(self):
        return self.shown_name

    def get_short_name(self):
        return self.shown_name


class EmailCode(models.Model):
    """A six-digit code sent to an address. Neither the address nor the code is kept: both are HMAC digests keyed
    on SECRET_KEY, so the table names nobody."""

    class Purpose(models.TextChoices):
        PROVE = 'prove', 'Prove the address'

    email_digest = models.CharField(max_length=64)
    purpose = models.CharField(max_length=8, choices=Purpose.choices)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='+')
    code_digest = models.CharField(max_length=64)
    tries = models.PositiveSmallIntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'accounts_email_code'
        indexes = [models.Index(fields=['email_digest', 'purpose'], name='accounts_code_lookup_idx')]
