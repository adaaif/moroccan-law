"""Who may take a data file of an edition while it is given on request, what is kept when one leaves, and the
holder's receipt.

A data file goes to an access that includes the database, identified one of three ways: its key (`X-Api-Key`, read by
`keys.holder`), the account signed in (the site's JWT), or a ticket: a signed address the account asked for, good for
ten minutes, bound to its access, the edition and the file, so that a browser can follow a plain link. Each file given
is a `Download` row; an access takes at most ACCESS_DOWNLOADS_A_DAY files a day of Morocco's. The same file of the same
edition asked again that day (a download resumed, a second try) is given without a new row."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.utils import timezone

from apps.opendata.models import Access, Download
from apps.opendata.services import editions, keys

RECEIPT = 'RECEIPT.txt'
TICKET_SECONDS = 600
SALT = 'apps.opendata.ticket'


class Refusal(Exception):
    """A refusal of the door: its HTTP status, the error's field and code, and for the day's limit the seconds until
    it opens again."""

    def __init__(self, status: int, field: str, code: str, retry: int | None = None):
        super().__init__(code)
        self.status, self.field, self.code, self.retry = status, field, code, retry


@dataclass(frozen=True)
class Taker:
    """The access a file goes to, and how it was identified (a ticket counts as the account's)."""
    access: int
    by: str


def _usable(**match):
    return Access.objects.filter(state=Access.State.LIVE, ends_on__gte=timezone.localdate(), data=True, **match)


def _ticket(token: str, edition: editions.Edition, name: str) -> Taker:
    try:
        held = signing.loads(token, salt=SALT, max_age=TICKET_SECONDS)
    except signing.SignatureExpired:
        raise Refusal(401, 'ticket', 'expired') from None
    except signing.BadSignature:
        raise Refusal(401, 'ticket', 'invalid') from None
    if not isinstance(held, dict) or (held.get('e'), held.get('f')) != (edition.date, name):
        raise Refusal(401, 'ticket', 'invalid')
    if not isinstance(held.get('a'), int) or not _usable(pk=held['a']).exists():
        raise Refusal(403, 'open_data', 'no_access')
    return Taker(held['a'], Download.By.ACCOUNT)


def taker(request, token: str, edition: editions.Edition, name: str) -> Taker:
    """Who asks for `name` of `edition`: a key (a `keys.Refused` when it opens nothing), a ticket, or the account
    signed in. `Refusal` when nothing identifies the caller or their access does not include the database."""
    holder = keys.holder(request)
    if token:
        return _ticket(token, edition, name)
    if holder:
        if not holder.data:
            raise Refusal(403, 'open_data', 'no_access')
        return Taker(holder.access, Download.By.KEY)
    # The account its session names (the view reads the token only now: a token that does not hold is DRF's 401).
    user = request.user
    if not user.is_authenticated:
        raise Refusal(401, 'open_data', 'request')
    access = Access.live_of(user)
    if access is None or not access.data:
        raise Refusal(403, 'open_data', 'no_access')
    return Taker(access.pk, Download.By.ACCOUNT)


def give(taker: Taker, edition: editions.Edition, name: str) -> None:
    """Count a data file leaving an access and keep its row; `Refusal` (429) past the day's files."""
    start = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    taken = set(Download.objects.filter(access_id=taker.access, at__gte=start).values_list('edition', 'file'))
    if (edition.date, name) in taken:
        return
    if len(taken) >= settings.ACCESS_DOWNLOADS_A_DAY:
        retry = int((start + timedelta(days=1) - timezone.now()).total_seconds()) + 1
        raise Refusal(429, 'open_data', 'daily', retry=retry)
    Download.objects.create(access_id=taker.access, edition=edition.date, file=name,
                            sha256=(edition.file(name) or {}).get('sha256', ''), by=taker.by)


def ticket(user, asked, name) -> str:
    """The address of one file of one edition for the account's access, signed and good for ten minutes."""
    if not isinstance(name, str) or (name not in editions.DATA and name != RECEIPT):
        raise Refusal(400, 'file', 'invalid')
    edition = editions.find(asked) if isinstance(asked, str) else None
    if edition is None:
        raise Refusal(400, 'edition', 'unknown')
    access = _usable(user=user).first()
    if access is None:
        raise Refusal(403, 'open_data', 'no_access')
    token = signing.dumps({'a': access.pk, 'e': edition.date, 'f': name}, salt=SALT)
    return f'/api/open/{asked}/{name}?{urlencode({"t": token})}'


def receipt(taker: Taker, edition: editions.Edition) -> str:
    """The holder's proof of their copy: who holds it, which access, the edition by its date and manifest's hash, the
    terms they accepted and the licence, in Arabic and in French."""
    access = Access.objects.select_related('request').get(pk=taker.access)
    holder, terms, today = access.request.name, access.request.terms, timezone.localdate().isoformat()
    site = settings.SITE_NAME
    return f"""إيصال نسخة من قاعدة بيانات «قانون» ({site})

الحامل: {holder}
رقم الوصول: {access.pk}
النسخة: {edition.date}
بصمة البيان manifest.json (SHA-256): {edition.sha256}
الشروط المقبولة: شروط {terms}
الرخصة: رخصة قاعدة البيانات المفتوحة (ODbL 1.0)؛ النصوص الرسمية لا يحميها حق المؤلف (القانون رقم 2.00، المادة 8)
حُرِّر في: {today}

بيان النسخة يذكر بصمة كل ملف من ملفاتها: قارن بصمة manifest.json بهذه، ثم بصمة كل ملف بما يذكره البيان. وحده النص
المنشور في الجريدة الرسمية يُعتدّ به.


Reçu d'une copie de la base de données de {site} («قانون»)

Titulaire : {holder}
Accès n° : {access.pk}
Édition : {edition.date}
Empreinte du manifeste manifest.json (SHA-256) : {edition.sha256}
Conditions acceptées : conditions du {terms}
Licence : Open Database License (ODbL 1.0) ; les textes officiels ne sont pas protégés par le droit d'auteur (loi
n° 2-00, art. 8)
Établi le : {today}

Le manifeste de l'édition donne l'empreinte de chacun de ses fichiers : comparez celle de manifest.json à celle-ci,
puis celle de chaque fichier à ce qu'en dit le manifeste. Seul le texte publié au Bulletin officiel fait foi.
"""
