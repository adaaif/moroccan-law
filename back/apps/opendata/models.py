"""Access on request: the database and the API for outside programs are given to a person the site's staff accepted.

- `Request`: what an account asked for and what was decided. One open request an account.
- `Access`: what an accepted account holds: the API, the database or both, a size of limits and an end date. One live
  access an account.
- `ApiKey`: a key its holder made for an access, sent as `X-Api-Key`. Only its hash is kept; the key is shown once, to
  its holder, when made.
- `AccessDay`: what an access used in a day of Morocco's: calls and articles, by door. Counts only: never what was
  asked, never an address.
- `Download`: a file of an edition given to an access.
- `Event`: one line for each act on a request or an access (sent, asked, accepted, changed, renewed, ended…): who,
  when, what. The history a sheet shows, and the log of every decision.

The limits and the day's counts belong to the access, not to the key: two keys of one access (one replacing the other)
share one allowance."""
import hashlib
import secrets
import string
import zlib

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

PREFIX = 'law_'
ALPHABET = string.digits + string.ascii_letters
BODY, CHECK = 32, 6


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _checksum(body: str) -> str:
    """Six characters said of a key's body (its CRC-32, in the key's alphabet): a mistyped key is told apart from a
    real one without asking the database."""
    n, out = zlib.crc32(body.encode()), ''
    for _ in range(CHECK):
        n, r = divmod(n, len(ALPHABET))
        out = ALPHABET[r] + out
    return out


def new_key() -> str:
    body = ''.join(secrets.choice(ALPHABET) for _ in range(BODY))
    return PREFIX + body + _checksum(body)


def well_formed(key: str) -> bool:
    """Whether `key` has a key's shape and its checksum: said before any lookup."""
    if not isinstance(key, str) or len(key) != len(PREFIX) + BODY + CHECK or not key.startswith(PREFIX):
        return False
    body, check = key[len(PREFIX):-CHECK], key[-CHECK:]
    return all(c in ALPHABET for c in body) and secrets.compare_digest(_checksum(body), check)


class Request(models.Model):
    """What an account asked for, in six answers, and what was decided."""

    class Kind(models.TextChoices):
        PERSON = 'person', 'A person'
        SCHOOL = 'school', 'A university or a school'
        NEWSROOM = 'newsroom', 'A newsroom'
        ASSOCIATION = 'association', 'An association'
        PUBLIC = 'public', 'A public body'
        COMPANY = 'company', 'A company'

    class Volume(models.TextChoices):
        SMALL = 'small', 'Small'
        MEDIUM = 'medium', 'Medium'
        LARGE = 'large', 'Large'

    class State(models.TextChoices):
        WAITING = 'waiting', 'Waiting for an answer'
        MORE = 'more', 'More was asked of the person'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'

    class Reason(models.TextChoices):
        """Why a request is declined: one of five, said to the person as a code the web translates."""
        UNCLEAR = 'unclear', 'The use is not clear: say more'
        IDENTITY = 'identity', 'We cannot tell who asks'
        SCOPE = 'scope', 'More is asked than the use needs'
        TERMS = 'terms', 'The use breaks the terms'
        LATER = 'later', 'Not now'

    OPEN = (State.WAITING, State.MORE)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='access_requests')
    # Who asks.
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    # What they will build or study.
    purpose = models.TextField(max_length=600)
    wants_api = models.BooleanField(default=False)
    wants_data = models.BooleanField(default=False)
    # Where it will run, if it has an address.
    runs_at = models.CharField(max_length=200, blank=True, default='', db_default='')
    volume = models.CharField(max_length=6, choices=Volume.choices)
    commercial = models.BooleanField(default=False)
    # The terms accepted with the request: their date is their version (settings.ACCESS_TERMS).
    terms = models.CharField(max_length=10)

    state = models.CharField(max_length=8, choices=State.choices, default=State.WAITING, db_default=State.WAITING)
    # The one line asked of the person, and what they answered.
    asked = models.CharField(max_length=300, blank=True, default='', db_default='')
    answer = models.TextField(max_length=600, blank=True, default='', db_default='')
    reason = models.CharField(max_length=8, choices=Reason.choices, blank=True, default='', db_default='')
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    # A request to change an access the account already holds (add the database, a bigger size): that access. What it
    # asks to hold afterwards is `wants_api` / `wants_data` and `wanted_size`; `purpose` says why. Accepted, the access
    # is changed in place and its keys keep working.
    change_of = models.ForeignKey('Access', null=True, blank=True, on_delete=models.CASCADE, related_name='changes')
    wanted_size = models.CharField(max_length=8, blank=True, default='', db_default='')
    # Since when it has waited for the staff: when it was sent, then when its account answered what was asked. The day
    # an answer is due is counted from here.
    waiting_since = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'opendata_request'
        constraints = [
            models.UniqueConstraint(fields=['user'], condition=Q(state__in=('waiting', 'more')),
                                    name='opendata_request_one_open'),
        ]
        indexes = [models.Index(fields=['state', 'created_at'], name='opendata_request_queue_idx')]

    def __str__(self):
        return f'{self.name} ({self.get_state_display()})'


class Access(models.Model):
    """What an accepted account holds, until its end date or until it is ended."""

    class Size(models.TextChoices):
        TRY = 'try', 'Try'
        APP = 'app', 'App'
        PARTNER = 'partner', 'Partner (its own numbers)'

    class State(models.TextChoices):
        LIVE = 'live', 'Live'
        ENDED = 'ended', 'Ended'

    class Ended(models.TextChoices):
        ASKED = 'asked', 'The holder asked'
        TERMS = 'terms', 'The terms'
        LEAKED = 'leaked', 'A key leaked'
        UNUSED = 'unused', 'Unused'
        EXPIRED = 'expired', 'Its end date passed'
        ACCOUNT = 'account', 'The account was deleted'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accesses')
    request = models.OneToOneField(Request, on_delete=models.PROTECT, related_name='access')
    api = models.BooleanField(default=False)
    data = models.BooleanField(default=False)
    size = models.CharField(max_length=8, choices=Size.choices, default=Size.TRY, db_default=Size.TRY)
    # A partner's own numbers; empty for the two named sizes (settings.ACCESS_SIZES).
    minute = models.PositiveIntegerField(null=True, blank=True)
    calls = models.PositiveIntegerField(null=True, blank=True)
    articles = models.PositiveIntegerField(null=True, blank=True)
    ends_on = models.DateField()
    state = models.CharField(max_length=6, choices=State.choices, default=State.LIVE, db_default=State.LIVE)
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_reason = models.CharField(max_length=8, choices=Ended.choices, blank=True, default='', db_default='')
    ended_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='+')
    renewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'opendata_access'
        verbose_name_plural = 'accesses'
        constraints = [
            models.UniqueConstraint(fields=['user'], condition=Q(state='live'), name='opendata_access_one_live'),
        ]
        indexes = [models.Index(fields=['state', 'ends_on'], name='opendata_access_ends_idx')]

    def __str__(self):
        return f'{self.user_id}: {self.size} ({self.state})'

    def limits(self) -> dict:
        """The access's three limits: requests a minute, calls a day, articles a day."""
        named = settings.ACCESS_SIZES['app' if self.size == self.Size.PARTNER else self.size]
        if self.size != self.Size.PARTNER:
            return dict(named)
        return {'minute': self.minute or named['minute'], 'calls': self.calls or named['calls'],
                'articles': self.articles or named['articles']}

    @property
    def usable(self) -> bool:
        """Live, and its end date not passed (the night's job ends it; until it runs, the date decides)."""
        return self.state == self.State.LIVE and self.ends_on >= timezone.localdate()

    @classmethod
    def live_of(cls, user) -> 'Access | None':
        """The access an account may use today, if it holds one."""
        if not getattr(user, 'is_authenticated', False):
            return None
        return cls.objects.filter(user=user, state=cls.State.LIVE, ends_on__gte=timezone.localdate()).first()


class ApiKey(models.Model):
    """A key of an access, made by its holder. `key_hash` is all that is kept of it."""

    access = models.ForeignKey(Access, on_delete=models.CASCADE, related_name='keys')
    name = models.CharField(max_length=60, blank=True, default='', db_default='',
                            help_text='What its holder calls it: «the server», «tests».')
    prefix = models.CharField(max_length=12, help_text='The first characters, to recognise it.')
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # The last day of Morocco's it was used: written once a day.
    last_used_on = models.DateField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'opendata_api_key'
        indexes = [models.Index(fields=['access', 'ended_at'], name='opendata_key_access_idx')]

    def __str__(self):
        return f'{self.name or "key"} ({self.prefix}…)'

    @classmethod
    def issue(cls, access: Access, name: str = '') -> tuple['ApiKey', str]:
        """A new key of `access`, and the key itself: this is the only time it exists outside its holder's hands."""
        key = new_key()
        return cls.objects.create(access=access, name=name[:60], prefix=key[:12], key_hash=hash_key(key)), key


class AccessDay(models.Model):
    """What an access used in a day of Morocco's. Counts only: no question, no address."""

    access = models.ForeignKey(Access, on_delete=models.CASCADE, related_name='days')
    day = models.DateField()
    calls = models.PositiveIntegerField(default=0, db_default=0)
    articles = models.PositiveIntegerField(default=0, db_default=0)
    # Calls by door: {'v1.search': 12, 'v1.articles': 3, 'mcp': 4, 'site': 1}.
    doors = models.JSONField(default=dict)
    # Calls refused because a limit was reached, by limit: {'minute': 3, 'calls': 0, 'articles': 1}.
    limits = models.JSONField(default=dict)

    class Meta:
        db_table = 'opendata_access_day'
        constraints = [models.UniqueConstraint(fields=['access', 'day'], name='opendata_access_day_unique')]


class Download(models.Model):
    """A file of an edition given to an access: who took which edition, and when."""

    class By(models.TextChoices):
        ACCOUNT = 'account', 'Signed in, from the account page'
        KEY = 'key', 'With a key'

    access = models.ForeignKey(Access, on_delete=models.CASCADE, related_name='downloads')
    edition = models.CharField(max_length=10)          # the edition's date, YYYY-MM-DD
    file = models.CharField(max_length=60)
    sha256 = models.CharField(max_length=64, blank=True, default='', db_default='')
    by = models.CharField(max_length=7, choices=By.choices)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'opendata_download'
        indexes = [models.Index(fields=['access', 'at'], name='opendata_download_access_idx')]


class Event(models.Model):
    """One act on a request or an access: who did it, when, and what. Written by the services, never typed. The
    history of a request and of an access, and the log of every decision, whichever door it was made at."""

    class Act(models.TextChoices):
        SENT = 'sent', 'The account sent a request'
        ANSWERED = 'answered', 'The account answered what was asked'
        ASKED = 'asked', 'The staff asked for more'
        ACCEPTED = 'accepted', 'The staff accepted'
        DECLINED = 'declined', 'The staff declined'
        CHANGED = 'changed', 'What an access holds, or its size, was changed'
        RENEWED = 'renewed', 'An access was given a new end date'
        ENDED = 'ended', 'An access ended'
        KEY_MADE = 'key_made', 'Its holder made a key'
        KEY_ENDED = 'key_ended', 'A key was ended'

    at = models.DateTimeField(auto_now_add=True)
    # Who did it: a superuser for a decision, the account for its own acts, nobody for the night's job.
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    request = models.ForeignKey(Request, null=True, blank=True, on_delete=models.CASCADE, related_name='events')
    access = models.ForeignKey(Access, null=True, blank=True, on_delete=models.CASCADE, related_name='events')
    act = models.CharField(max_length=10, choices=Act.choices)
    # What the act set, as codes and numbers: the size and what was granted, a reason, a date, the line asked. Never a
    # key, and nothing the account typed.
    details = models.JSONField(default=dict)

    class Meta:
        db_table = 'opendata_event'
        indexes = [models.Index(fields=['-at'], name='opendata_event_at_idx'),
                   models.Index(fields=['request', 'at'], name='opendata_event_request_idx'),
                   models.Index(fields=['access', 'at'], name='opendata_event_access_idx')]

    def __str__(self):
        return f'{self.act} ({self.at:%Y-%m-%d})'
