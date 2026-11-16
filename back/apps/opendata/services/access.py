"""An access after its request was accepted: shown to its holder, changed and renewed by the staff, ended (by the
staff, by its holder, by the account's deletion, or by its end date passing), and the letter 30 days before its end.

Ending an access ends every live key of it in the same few writes, whatever the number of accesses ended: the keys are
marked ended and each is dropped from what is kept between requests (`keys.forget`), so its next request is refused.
Changing or renewing one drops its keys from what is kept the same way, so they keep working with the new limits at
once. Every act leaves an event (services/log.py), and a letter tells the holder; the letters go after the writes, and
one that cannot go never undoes them (apps/accounts/services/mail.py)."""
import calendar
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.services import mail
from apps.accounts.services.refusals import Refused
from apps.opendata.models import Access, AccessDay, ApiKey, Download, Event, Request
from apps.opendata.services import keys, log

# The holder is written to this many days before the end date.
WARN_DAYS = 30
# What the staff may end an access for; the holder's own end (`asked`), the end date (`expired`) and the account's
# deletion (`account`) are said by the code.
BY_THE_STAFF = (Access.Ended.TERMS, Access.Ended.LEAKED, Access.Ended.UNUSED)
# What an access holds, as its events say it before and after a change.
HELD = ('api', 'data', 'size', 'minute', 'calls', 'articles')
# A request's answers a person typed: emptied when the account is deleted, and by the retention /privacy states
# (services/requests.py `forget_typed`).
TYPED = {'name': '', 'purpose': '', 'runs_at': '', 'answer': '', 'asked': ''}


def months_after(day: date, months: int) -> date:
    """The same day `months` later (earlier when negative); the month's last day when it has fewer days."""
    y, m = divmod(day.month - 1 + months, 12)
    year, month = day.year + y, m + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def default_end(today: date | None = None) -> date:
    """The end date an access is given unless the staff chooses another: ACCESS_MONTHS from today."""
    return months_after(today or timezone.localdate(), settings.ACCESS_MONTHS)


def granted(api: bool, data: bool) -> str:
    """The code of what was asked or granted, for the letters' words: `api`, `data` or `both`."""
    return 'both' if api and data else 'api' if api else 'data'


def day(d: date) -> str:
    return f'{d:%d/%m/%Y}'


def page() -> str:
    """The access's own page on the site, which every access letter links to."""
    return f'{settings.SITE_URL.rstrip("/")}/data/access'


def _words(user, api: bool, data: bool, words: dict) -> dict:
    return {'granted': mail.ACCESS_WORDS[mail.language(user)]['granted'][granted(api, data)], 'account': page(),
            **words}


def letter(user, code: str, *, api: bool, data: bool, **words) -> mail.Letter:
    """One of the access letters, made and not sent: what `write_to` sends, as the desk shows it before a decision."""
    return mail.compose(user, code, **_words(user, api, data, words))


def write_to(user, code: str, *, api: bool, data: bool, **words) -> bool:
    """One of the access letters to the account, in its language, with what it asked or holds in words and the link to
    the access's page."""
    return mail.send(user, code, **_words(user, api, data, words))


def held(access: Access) -> dict:
    """What an access holds, as its events keep it: what it opens, its size and a partner's own numbers."""
    return {name: getattr(access, name) for name in HELD}


def holding(access: Access) -> dict:
    """The words of a letter that says what an access holds now: its end date and its three limits."""
    return {'ends_on': day(access.ends_on), **access.limits()}


# The most a partner's number may be: what its column holds.
NUMBER_MOST = 2**31 - 1


def numbers(size: str, minute=None, calls=None, articles=None) -> dict:
    """A partner's three numbers, checked (a whole number from 1 to NUMBER_MOST, or None for the app size's); a named
    size carries the settings' numbers, so none of its own."""
    given = {'minute': minute, 'calls': calls, 'articles': articles}
    for name, n in given.items():
        if n is not None and (isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= NUMBER_MOST):
            raise Refused(name, 'invalid')
    return given if size == Access.Size.PARTNER else dict.fromkeys(given)


def live_hashes(access_id: int) -> list[str]:
    return list(ApiKey.objects.filter(access_id=access_id, ended_at=None).values_list('key_hash', flat=True))


def reason_words(user, kind: str, code: str) -> str:
    """Why, in the account's language: `kind` is `declined` or `ended`."""
    return mail.ACCESS_WORDS[mail.language(user)][kind][code]


def shown(access: Access | None) -> dict | None:
    """An access as its holder's account page reads it (GET /api/access/). An access whose end date passed is said
    ended (`expired`) before the night's job writes it so."""
    if access is None:
        return None
    usable = access.usable
    return {'id': access.pk, 'api': access.api, 'data': access.data, 'size': access.size, 'limits': access.limits(),
            'ends_on': access.ends_on, 'state': Access.State.LIVE if usable else Access.State.ENDED,
            'ended_reason': access.ended_reason or ('' if usable else Access.Ended.EXPIRED),
            'created_at': access.created_at}


def _by_staff(by) -> None:
    if not getattr(by, 'is_superuser', False):
        raise Refused('by', 'not_superuser', 403)


def _locked(access: Access, *, usable: bool = False) -> Access:
    """The access's row read again under a lock, with its account; refused when it is ended (or, with `usable`, past
    its end date too)."""
    row = (Access.objects.select_for_update(of=('self',)).select_related('user')
           .filter(pk=access.pk, state=Access.State.LIVE).first())
    if row is None or (usable and not row.usable):
        raise Refused('access', 'ended', 409)
    return row


def forget_keys(hashes: list[str]) -> None:
    """Drop the keys from what is kept between requests: now, and again once the writes are committed, so a request
    between the two cannot keep an old reading of the access alive inside a longer transaction (the account's
    deletion)."""
    def drop():
        for h in hashes:
            keys.forget(h)
    drop()
    transaction.on_commit(drop)


def end_rows(rows, reason: str, by=None) -> list[Access]:
    """End the live accesses among `rows` (a queryset) and every live key of them, in five queries whatever their
    number, one event each. Their rows come back, with their accounts, ended; nobody is written to here. `by` is who
    ended them: a superuser, the holder for their own, nobody for the night's job or the account's deletion."""
    if reason not in Access.Ended.values:
        raise Refused('reason', 'invalid')
    now = timezone.now()
    with transaction.atomic():
        ending = list(rows.filter(state=Access.State.LIVE).select_related('user').select_for_update(of=('self',)))
        if not ending:
            return []
        ids = [a.pk for a in ending]
        Access.objects.filter(pk__in=ids).update(state=Access.State.ENDED, ended_reason=reason, ended_by=by,
                                                 ended_at=now)
        live = list(ApiKey.objects.filter(access_id__in=ids, ended_at=None).values_list('pk', 'key_hash'))
        if live:
            ApiKey.objects.filter(pk__in=[pk for pk, _ in live]).update(ended_at=now)
        log.note_each(Event.Act.ENDED, ending, by=by, reason=reason)
    for a in ending:
        a.state, a.ended_reason, a.ended_by, a.ended_at = Access.State.ENDED, reason, by, now
    forget_keys([h for _, h in live])
    return ending


def _tell_ended(ended: list[Access]) -> None:
    for a in ended:
        write_to(a.user, 'access_ended', api=a.api, data=a.data,
                 reason=reason_words(a.user, 'ended', a.ended_reason))


def end(access: Access, reason: str, by=None) -> Access:
    """End one access: its state, the reason, who and when; its live keys; a letter to its holder (none when the
    account is being deleted). An access already ended is left as it was."""
    ended = end_rows(Access.objects.filter(pk=access.pk), reason, by)
    if ended:
        a = ended[0]
        access.state, access.ended_reason, access.ended_by, access.ended_at = a.state, a.ended_reason, by, a.ended_at
        if reason != Access.Ended.ACCOUNT:
            _tell_ended(ended)
    return access


def end_by_staff(access: Access, by, reason: str) -> Access:
    """A superuser ends a live access for one of the staff's reasons (BY_THE_STAFF); its keys stop at once and a
    letter tells the holder why."""
    _by_staff(by)
    if reason not in BY_THE_STAFF:
        raise Refused('reason', 'invalid')
    if not Access.objects.filter(pk=access.pk, state=Access.State.LIVE).exists():
        raise Refused('access', 'ended', 409)
    return end(access, reason, by=by)


def end_own(user) -> Access:
    """The holder ends their own access (POST /api/access/end/); the letter that it ended is the confirmation."""
    access = Access.objects.filter(user=user, state=Access.State.LIVE).first()
    if access is None:
        raise Refused('access', 'none', 403)
    return end(access, Access.Ended.ASKED, by=user)


def renew(access: Access, by, ends_on: date | None = None) -> Access:
    """A live access given a new end date: ACCESS_MONTHS from today unless the staff chooses one. Only a superuser
    renews. Its keys go on with the new date at once; a letter tells the holder."""
    _by_staff(by)
    today = timezone.localdate()
    ends_on = ends_on or default_end(today)
    if ends_on <= today:
        raise Refused('ends_on', 'past')
    with transaction.atomic():
        row = _locked(access)
        before = row.ends_on
        row.ends_on, row.renewed_at = ends_on, timezone.now()
        row.save(update_fields=['ends_on', 'renewed_at'])
        log.note(Event.Act.RENEWED, by=by, access=row, ends_on=ends_on, before=before)
        hashes = live_hashes(row.pk)
    forget_keys(hashes)
    access.ends_on, access.renewed_at = row.ends_on, row.renewed_at
    write_to(row.user, 'access_renewed', api=row.api, data=row.data, ends_on=day(row.ends_on))
    return access


def change(access: Access, by, *, api: bool | None = None, data: bool | None = None, size: str | None = None,
           minute: int | None = None, calls: int | None = None, articles: int | None = None) -> Access:
    """The staff changes what a live access holds: the API, the database, its size, a partner's three numbers (what
    is left out stays). It must still open the API or the database; a named size carries the settings' numbers, a
    partner its own (those left out stay, or take the app size's). Its keys keep working, with the new limits at once;
    a letter tells the holder what they hold now. Refused when nothing would change."""
    _by_staff(by)
    if size is not None and size not in Access.Size.values:
        raise Refused('size', 'invalid')
    for name, value in (('api', api), ('data', data)):
        if value is not None and not isinstance(value, bool):
            raise Refused(name, 'invalid')
    numbers(Access.Size.PARTNER, minute, calls, articles)           # checked before anything is read
    with transaction.atomic():
        row = _locked(access, usable=True)
        before = held(row)
        after = {'api': row.api if api is None else api, 'data': row.data if data is None else data,
                 'size': size or row.size}
        if not (after['api'] or after['data']):
            raise Refused('wants', 'required')
        given = {'minute': minute, 'calls': calls, 'articles': articles}
        kept = row.size == Access.Size.PARTNER
        after.update(numbers(after['size'], **{n: v if v is not None else (before[n] if kept else None)
                                               for n, v in given.items()}))
        if after == before:
            raise Refused('change', 'nothing')
        for name, value in after.items():
            setattr(row, name, value)
        row.save(update_fields=list(HELD))
        log.note(Event.Act.CHANGED, by=by, access=row, before=before, after=after)
        hashes = live_hashes(row.pk)
    forget_keys(hashes)
    for name in HELD:
        setattr(access, name, getattr(row, name))
    write_to(row.user, 'access_changed', api=row.api, data=row.data, **holding(row))
    return access


def expire(today: date | None = None) -> int:
    """The night's job: every live access whose end date passed is ended (`expired`), and its holder told."""
    today = today or timezone.localdate()
    ended = end_rows(Access.objects.filter(state=Access.State.LIVE, ends_on__lt=today), Access.Ended.EXPIRED)
    _tell_ended(ended)
    return len(ended)


def warn(today: date | None = None) -> int:
    """The night's job: a letter to each holder whose access ends in exactly WARN_DAYS days."""
    today = today or timezone.localdate()
    ending = list(Access.objects.filter(state=Access.State.LIVE, ends_on=today + timedelta(days=WARN_DAYS))
                  .select_related('user'))
    for a in ending:
        write_to(a.user, 'access_ending', api=a.api, data=a.data, ends_on=day(a.ends_on))
    return len(ending)


def export(user) -> dict:
    """What the account's export holds of its access (law 09-08): its requests, accesses, day counts and downloads, and
    the acts on them (the act, its day and its details; not who did it). Never a key, nor its hash. Five queries."""
    accesses = list(Access.objects.filter(user=user).order_by('created_at'))
    events = Event.objects.filter(Q(request__user=user) | Q(access__user=user)).order_by('at', 'pk')
    return {
        'access_requests': [
            {'id': r.pk, 'name': r.name, 'kind': r.kind, 'purpose': r.purpose, 'wants_api': r.wants_api,
             'wants_data': r.wants_data, 'runs_at': r.runs_at, 'volume': r.volume, 'commercial': r.commercial,
             'terms': r.terms, 'state': r.state, 'asked': r.asked, 'answer': r.answer, 'reason': r.reason,
             'created_at': r.created_at, 'decided_at': r.decided_at}
            for r in Request.objects.filter(user=user).order_by('created_at')],
        'accesses': [
            {'id': a.pk, 'request': a.request_id, 'api': a.api, 'data': a.data, 'size': a.size, 'limits': a.limits(),
             'ends_on': a.ends_on, 'state': a.state, 'ended_reason': a.ended_reason, 'created_at': a.created_at,
             'renewed_at': a.renewed_at, 'ended_at': a.ended_at}
            for a in accesses],
        'access_days': [
            {'access': d.access_id, 'day': d.day, 'calls': d.calls, 'articles': d.articles, 'doors': d.doors}
            for d in AccessDay.objects.filter(access__user=user).order_by('day', 'access_id')],
        'downloads': [
            {'access': d.access_id, 'edition': d.edition, 'file': d.file, 'sha256': d.sha256, 'by': d.by, 'at': d.at}
            for d in Download.objects.filter(access__user=user).order_by('at')],
        'access_events': [
            {'act': e.act, 'day': timezone.localdate(e.at), 'request': e.request_id, 'access': e.access_id,
             'details': e.details}
            for e in events],
    }


def leave(user) -> None:
    """The account is being deleted: its access ends (`account`, no letter) and its requests lose what was typed in
    them. Their states, dates and codes stay, as the counts read them."""
    end_rows(Access.objects.filter(user=user), Access.Ended.ACCOUNT)
    Request.objects.filter(user=user).exclude(**TYPED).update(**TYPED)
