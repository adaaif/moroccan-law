"""A request for access, from the account that sends it to the staff's answer.

- `body(user)`: what GET /api/access/ answers, and every door of the request after it acts.
- `send`, `answer`, `change`: the account's acts: a request in six answers with the terms accepted; its answer to the
  one line the staff asked; a holder's request to change the access it holds (more, less, another size).
- `accept`, `ask`, `decline`: the staff's three answers. Only a superuser decides, never on their own request; each
  decision keeps who and when, and a letter goes each time. Accepting a change request changes its access in place.
  `letter_of` makes the letter an answer would send, without sending it or writing anything.
- `due_on`, `days_left`: the day an answer is due, ACCESS_ANSWER_DAYS working days after the request began to wait.
- `counted`, `lines`, `decisions`: the queue's few figures and the week's decisions, for the admin's lists, the desk
  and the Monday letter.
- `forget_typed`: the retention /privacy states: a declined request's typed answers are emptied six months after the
  decision, an ended access's request twelve months after it ended.

The kinds, the volumes and the reasons travel as codes; the web translates them."""
import statistics
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Min, Q
from django.urls import reverse
from django.utils import timezone

from apps.accounts.services import mail
from apps.accounts.services.accounts import AccountError
from apps.accounts.services.refusals import Refused
from apps.opendata.models import Access, Event, Request
from apps.opendata.services import access as accesses
from apps.opendata.services import gate, log

# The typed answers: (most characters, needed, on one line). A name and an address are one line: a line break typed in
# them would also break the subject of the staff's letter.
TEXTS = {'name': (120, True, True), 'purpose': (600, True, False), 'runs_at': (200, False, True)}
CHOICES = {'kind': Request.Kind.values, 'volume': Request.Volume.values}
ANSWER_MOST = 600
LINE_MOST = 300
WHY_MOST = 600
# The sizes a change request may name; '' leaves the size as it is.
SIZES_ASKED = ('', *Access.Size.values)
# The size accepting proposes from the volume a request named (unless it named a size).
SIZE_OF_VOLUME = {Request.Volume.SMALL: Access.Size.TRY, Request.Volume.MEDIUM: Access.Size.APP,
                  Request.Volume.LARGE: Access.Size.PARTNER}
# What /privacy promises: a declined request's typed answers kept this many months after the decision, an ended
# access's request this many after it ended.
DECLINED_MONTHS, ENDED_MONTHS = 6, 12
# The figures' window, and the queries `counted` costs (the Monday letter's test holds it to them).
WINDOW_DAYS = 30
QUERIES = 3
# The week's decisions in the Monday letter: their lines, and the queries they cost.
DECISIONS_SHOWN = 10
DECISION_QUERIES = 2
# The acts that are the staff's decisions (an access ended or a key ended counts when someone other than its holder did
# it, and not the night's job).
DECIDED = (Event.Act.ASKED, Event.Act.ACCEPTED, Event.Act.DECLINED, Event.Act.CHANGED, Event.Act.RENEWED,
           Event.Act.ENDED, Event.Act.KEY_ENDED)


def _newest(user) -> Request | None:
    return Request.objects.filter(user=user).order_by('-created_at', '-pk').first()


def ask_again_on(request: Request | None) -> date | None:
    """The day a declined account may ask again, while it is still ahead; None when it may ask now."""
    if request is None or request.state != Request.State.DECLINED or request.decided_at is None:
        return None
    on = timezone.localdate(request.decided_at) + timedelta(days=settings.ACCESS_ASK_AGAIN_DAYS)
    return on if on > timezone.localdate() else None


def working_days_after(day: date, n: int) -> date:
    """The day `n` working days after `day`, counting Monday to Friday. Public holidays are not counted out: the
    promise /data prints is in working days, and the desk says it as such."""
    while n > 0:
        day += timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


def due_on(request: Request) -> date | None:
    """The day an answer is due: ACCESS_ANSWER_DAYS working days (Monday to Friday; public holidays not counted out)
    after the day of Morocco's the request began to wait (when sent, or when its account answered what was asked).
    None unless it waits for the staff."""
    if request.state != Request.State.WAITING:
        return None
    return working_days_after(timezone.localdate(request.waiting_since), settings.ACCESS_ANSWER_DAYS)


def days_left(due: date | None, today: date | None = None) -> int | None:
    """The working days from today until `due`: 0 on the day itself, negative once it passed (-1 the first working
    day late)."""
    if due is None:
        return None
    today = today or timezone.localdate()
    first, last, sign = (today, due, 1) if due >= today else (due, today, -1)
    n, d = 0, first
    while d < last:
        d += timedelta(days=1)
        n += d.weekday() < 5
    return sign * n


def shown(request: Request | None) -> dict | None:
    """A request as its account reads it."""
    if request is None:
        return None
    return {'id': request.pk, 'state': request.state, 'name': request.name, 'kind': request.kind,
            'purpose': request.purpose, 'wants_api': request.wants_api, 'wants_data': request.wants_data,
            'runs_at': request.runs_at, 'volume': request.volume, 'commercial': request.commercial,
            'terms': request.terms, 'asked': request.asked, 'answer': request.answer, 'reason': request.reason,
            'created_at': request.created_at, 'decided_at': request.decided_at,
            'ask_again_on': ask_again_on(request), 'due_on': due_on(request), 'change_of': request.change_of_id,
            'wanted_size': request.wanted_size}


def _desk(user) -> dict | None:
    """For an active superuser, what waits on the access desk (one count); None for everyone else."""
    if not (getattr(user, 'is_active', False) and getattr(user, 'is_superuser', False)):
        return None
    return {'waiting': Request.objects.filter(state=Request.State.WAITING).count()}


def body(user) -> dict:
    """Where access on request stands, its terms and sizes, the account's newest request and newest access (both
    None for a visitor), and for a superuser what waits on the desk. Two queries for an account (three for a
    superuser), none for a visitor."""
    request = access = None
    if getattr(user, 'is_authenticated', False):
        request = _newest(user)
        access = Access.objects.filter(user=user).order_by('-created_at', '-pk').first()
    return {'position': gate.position(), 'terms': settings.ACCESS_TERMS, 'answer_days': settings.ACCESS_ANSWER_DAYS,
            'sizes': settings.ACCESS_SIZES, 'request': shown(request), 'access': accesses.shown(access),
            'desk': _desk(user)}


def _words(value, field: str, most: int, needed: bool, errors: list, one_line: bool = False) -> str | None:
    """A typed answer trimmed (and folded to one line), or None with its refusal added to `errors`."""
    if value is None:
        value = ''
    if not isinstance(value, str):
        errors.append((field, 'invalid'))
        return None
    value = ' '.join(value.split()) if one_line else value.strip()
    if not value and needed:
        errors.append((field, 'required'))
    elif len(value) > most:
        errors.append((field, 'too_long'))
    else:
        return value
    return None


def _read(data) -> dict:
    """The six answers and the terms, checked; every refusal of a field at once (AccountError)."""
    found, errors = {}, []
    for field, (most, needed, one_line) in TEXTS.items():
        value = _words(data.get(field), field, most, needed, errors, one_line)
        if value is not None:
            found[field] = value
    for field, allowed in CHOICES.items():
        value = data.get(field)
        if value in (None, ''):
            errors.append((field, 'required'))
        elif not isinstance(value, str) or value not in allowed:
            errors.append((field, 'invalid'))
        else:
            found[field] = value
    for field in ('wants_api', 'wants_data'):
        value = data.get(field)
        if value is None or isinstance(value, bool):
            found[field] = bool(value)
        else:
            errors.append((field, 'invalid'))
    if 'wants_api' in found and 'wants_data' in found and not (found['wants_api'] or found['wants_data']):
        errors.append(('wants', 'required'))
    commercial = data.get('commercial')
    if commercial is None:
        errors.append(('commercial', 'required'))
    elif not isinstance(commercial, bool):
        errors.append(('commercial', 'invalid'))
    else:
        found['commercial'] = commercial
    terms = data.get('terms')
    if terms in (None, ''):
        errors.append(('terms', 'required'))
    elif not isinstance(terms, str):
        errors.append(('terms', 'invalid'))
    elif terms != settings.ACCESS_TERMS:
        errors.append(('terms', 'stale'))
    else:
        found['terms'] = terms
    # Law 09-08: the person ticks the box themselves; it is never ticked for them.
    if data.get('consent') is not True:
        errors.append(('consent', 'required'))
    if errors:
        raise AccountError(errors)
    return found


def send(user, data) -> Request:
    """An account's request: unless the position is `closed` (while it is `open` the files need no request, a key
    still does), from a proven address, with no live access, no request
    open and no decline in the last ACCESS_ASK_AGAIN_DAYS. A letter to the account, one to the staff."""
    if gate.position() == gate.CLOSED:
        raise Refused('access', 'closed', 403)
    if not user.email_proven_at:
        raise Refused('email', 'unproven', 403)
    if Access.live_of(user):
        raise Refused('access', 'live', 409)
    newest = _newest(user)
    if newest is not None and newest.state in Request.OPEN:
        raise Refused('request', 'open', 409)
    if again := ask_again_on(newest):
        raise Refused('request', 'too_soon', 409, on=again.isoformat())
    found = _read(data)
    try:
        with transaction.atomic():
            made = Request.objects.create(user=user, **found)
    except IntegrityError:          # the same request sent twice at once: the database keeps one open
        raise Refused('request', 'open', 409) from None
    log.note(Event.Act.SENT, by=user, request=made, api=made.wants_api, data=made.wants_data, volume=made.volume)
    accesses.write_to(user, 'access_received', api=made.wants_api, data=made.wants_data, name=made.name,
                      days=settings.ACCESS_ANSWER_DAYS)
    _tell_staff(made, 'arrived')
    return made


def _read_change(data) -> dict:
    """What a change request asks: the API, the database (what the access is to hold afterwards), a size or '' to keep
    it, and why in the holder's words; every refusal of a field at once (AccountError)."""
    found, errors = {}, []
    for field in ('wants_api', 'wants_data'):
        value = data.get(field)
        if value is None or isinstance(value, bool):
            found[field] = bool(value)
        else:
            errors.append((field, 'invalid'))
    if 'wants_api' in found and 'wants_data' in found and not (found['wants_api'] or found['wants_data']):
        errors.append(('wants', 'required'))
    size = data.get('size')
    size = '' if size is None else size
    if not isinstance(size, str) or size not in SIZES_ASKED:
        errors.append(('size', 'invalid'))
    else:
        found['size'] = size
    why = _words(data.get('why'), 'why', WHY_MOST, True, errors)
    if errors:
        raise AccountError(errors)
    found['why'] = why
    return found


def change(user, data) -> Request:
    """A holder's request to change the access it holds (POST /api/access/change/): what it is to hold afterwards, a
    size if another, and why. Unless the position is `closed`, from an account with a usable access, no request open
    and no decline in the last ACCESS_ASK_AGAIN_DAYS. Who asks is copied from the access's own request. Refused when it
    asks for what is held already (a partner may ask for the partner size again: its numbers are its own). It waits
    for the staff like any request; the same letters go."""
    if gate.position() == gate.CLOSED:
        raise Refused('access', 'closed', 403)
    access = Access.live_of(user)
    if access is None:
        raise Refused('access', 'none', 403)
    newest = _newest(user)
    if newest is not None and newest.state in Request.OPEN:
        raise Refused('request', 'open', 409)
    if again := ask_again_on(newest):
        raise Refused('request', 'too_soon', 409, on=again.isoformat())
    found = _read_change(data)
    same_size = found['size'] == '' or (found['size'] == access.size and access.size != Access.Size.PARTNER)
    if (found['wants_api'], found['wants_data']) == (access.api, access.data) and same_size:
        raise Refused('change', 'nothing')
    origin = access.request
    try:
        with transaction.atomic():
            made = Request.objects.create(
                user=user, change_of=access, name=origin.name, kind=origin.kind, purpose=found['why'],
                wants_api=found['wants_api'], wants_data=found['wants_data'], runs_at=origin.runs_at,
                volume=origin.volume, commercial=origin.commercial, terms=origin.terms, wanted_size=found['size'])
    except IntegrityError:          # the same request sent twice at once: the database keeps one open
        raise Refused('request', 'open', 409) from None
    log.note(Event.Act.SENT, by=user, request=made, access=access, api=made.wants_api, data=made.wants_data,
             size=made.wanted_size)
    accesses.write_to(user, 'access_received', api=made.wants_api, data=made.wants_data, name=made.name,
                      days=settings.ACCESS_ANSWER_DAYS)
    made.change_of = access
    _tell_staff(made, 'arrived')
    return made


def answer(user, text) -> Request:
    """The account's answer to the line asked of it: the request waits for the staff again."""
    request = _newest(user)
    if request is None or request.state != Request.State.MORE:
        raise Refused('request', 'none', 409)
    request.user = user
    errors = []
    text = _words(text, 'answer', ANSWER_MOST, True, errors)
    if errors:
        raise Refused(*errors[0])
    request.answer, request.state, request.waiting_since = text, Request.State.WAITING, timezone.now()
    request.save(update_fields=['answer', 'state', 'waiting_since', 'updated_at'])
    log.note(Event.Act.ANSWERED, by=user, request=request)
    _tell_staff(request, 'answered')
    return request


def _may_decide(request: Request, by) -> None:
    if not getattr(by, 'is_superuser', False):
        raise Refused('by', 'not_superuser', 403)
    if by.pk == request.user_id:
        raise Refused('by', 'own', 403)


def _lock(request: Request) -> None:
    """Read the request's state again under a lock, inside the decision's transaction: two people deciding at once
    decide once."""
    state = Request.objects.select_for_update().filter(pk=request.pk).values_list('state', flat=True).first()
    if state not in Request.OPEN:
        raise Refused('request', 'decided', 409)


def _decided(request: Request, by, **fields) -> None:
    """Write a decision, with who and when."""
    for name, value in {**fields, 'decided_by': by, 'decided_at': timezone.now()}.items():
        setattr(request, name, value)
    request.save(update_fields=[*fields, 'decided_by', 'decided_at', 'updated_at'])


def _granting(request: Request, *, api, data, size, ends_on: date | None = None, minute=None, calls=None,
              articles=None) -> dict:
    """What accepting would grant, checked: the API, the database or both, a size, a partner's numbers, and the end
    date (ACCESS_MONTHS from today unless chosen; a change request keeps its access's unless one is chosen)."""
    if not (api or data):
        raise Refused('wants', 'required')
    if size not in Access.Size.values:
        raise Refused('size', 'invalid')
    numbers = accesses.numbers(size, minute, calls, articles)
    today = timezone.localdate()
    if ends_on is None and not request.change_of_id:
        ends_on = accesses.default_end(today)
    if ends_on is not None and ends_on <= today:
        raise Refused('ends_on', 'past')
    return {'api': bool(api), 'data': bool(data), 'size': size, 'ends_on': ends_on, **numbers}


def _held_after(request: Request, grant: dict, access: Access | None = None) -> Access:
    """The access as accepting leaves it, unsaved: a new one, or the change request's access with the grant on it."""
    if not request.change_of_id:
        return Access(user_id=request.user_id, request=request, **grant)
    access = access or request.change_of
    after = Access(**{name: getattr(access, name) for name in ('user_id', 'request_id', 'ends_on')})
    for name, value in grant.items():
        if value is not None or name != 'ends_on':
            setattr(after, name, value)
    return after


def _accepted_letter(request: Request, after: Access) -> tuple[str, dict]:
    code = 'access_change_accepted' if request.change_of_id else 'access_accepted'
    return code, {'api': after.api, 'data': after.data, 'name': request.name, **accesses.holding(after)}


def _line(line) -> str:
    errors = []
    line = _words(line, 'line', LINE_MOST, True, errors, one_line=True)
    if errors:
        raise Refused(*errors[0])
    return line


def _asked_letter(request: Request, line: str) -> tuple[str, dict]:
    return 'access_more', {'api': request.wants_api, 'data': request.wants_data, 'name': request.name, 'line': line}


def _declined_letter(request: Request, reason: str, on: date) -> tuple[str, dict]:
    again = on + timedelta(days=settings.ACCESS_ASK_AGAIN_DAYS)
    return 'access_declined', {'api': request.wants_api, 'data': request.wants_data, 'name': request.name,
                               'reason': accesses.reason_words(request.user, 'declined', reason),
                               'again': accesses.day(again)}


def accept(request: Request, by, *, api: bool, data: bool, size: str, ends_on: date | None = None,
           minute: int | None = None, calls: int | None = None, articles: int | None = None) -> Access:
    """Accept a request: its access is made with what the staff grants (it may be less than was asked), a size, and an
    end date (ACCESS_MONTHS from today unless chosen). A partner's three numbers are its own; an empty one takes the
    app size's. A letter tells the account what it holds and where to make its key.

    A change request changes its access in place instead: what it holds, its size and a partner's numbers, and its end
    date only when one is chosen. Its keys keep working, with the new limits at once; the letter says what it holds
    now."""
    _may_decide(request, by)
    grant = _granting(request, api=api, data=data, size=size, ends_on=ends_on, minute=minute, calls=calls,
                      articles=articles)
    if request.change_of_id:
        return _accept_change(request, by, grant)
    with transaction.atomic():
        _lock(request)
        if Access.live_of(request.user):
            raise Refused('access', 'live', 409)
        # A live access whose end date passed before the night's job ended it: ended now, so the new one may be live.
        accesses.end_rows(Access.objects.filter(user_id=request.user_id), Access.Ended.EXPIRED)
        _decided(request, by, state=Request.State.ACCEPTED)
        made = Access.objects.create(user_id=request.user_id, request=request, **grant)
        log.note(Event.Act.ACCEPTED, by=by, request=request, access=made, **accesses.held(made), ends_on=made.ends_on)
    code, words = _accepted_letter(request, made)
    accesses.write_to(request.user, code, **words)
    return made


def _accept_change(request: Request, by, grant: dict) -> Access:
    with transaction.atomic():
        _lock(request)
        access = (Access.objects.select_for_update().filter(pk=request.change_of_id, state=Access.State.LIVE)
                  .first())
        if access is None or not access.usable:
            raise Refused('access', 'ended', 409)
        before = accesses.held(access)
        after = _held_after(request, grant, access)
        for name in (*accesses.HELD, 'ends_on'):
            setattr(access, name, getattr(after, name))
        access.save(update_fields=[*accesses.HELD, 'ends_on'])
        _decided(request, by, state=Request.State.ACCEPTED)
        log.note(Event.Act.ACCEPTED, by=by, request=request, access=access, **accesses.held(access),
                 ends_on=access.ends_on, before=before)
        hashes = accesses.live_hashes(access.pk)
    accesses.forget_keys(hashes)
    code, words = _accepted_letter(request, access)
    accesses.write_to(request.user, code, **words)
    return access


def ask(request: Request, by, line) -> Request:
    """Ask the account for more, in one line: the request waits for its answer."""
    _may_decide(request, by)
    line = _line(line)
    with transaction.atomic():
        _lock(request)
        _decided(request, by, state=Request.State.MORE, asked=line, answer='')
        log.note(Event.Act.ASKED, by=by, request=request, line=line)
    code, words = _asked_letter(request, line)
    accesses.write_to(request.user, code, **words)
    return request


def decline(request: Request, by, reason) -> Request:
    """Decline a request for one of the five reasons; the account may ask again ACCESS_ASK_AGAIN_DAYS later."""
    _may_decide(request, by)
    if reason not in Request.Reason.values:
        raise Refused('reason', 'invalid')
    with transaction.atomic():
        _lock(request)
        _decided(request, by, state=Request.State.DECLINED, reason=reason)
        log.note(Event.Act.DECLINED, by=by, request=request, reason=reason)
    code, words = _declined_letter(request, reason, timezone.localdate(request.decided_at))
    accesses.write_to(request.user, code, **words)
    return request


def letter_of(request: Request, by, act: str, **fields) -> mail.Letter:
    """The letter `act` (`accept`, `ask` or `decline`) would send for `request`, with the act's own fields, made by
    the same words the act uses and not sent; nothing is written. Refused as the act would be."""
    _may_decide(request, by)
    if request.state not in Request.OPEN:
        raise Refused('request', 'decided', 409)
    if act == 'accept':
        grant = _granting(request, **fields)
        code, words = _accepted_letter(request, _held_after(request, grant))
    elif act == 'ask':
        code, words = _asked_letter(request, _line(fields.get('line')))
    elif act == 'decline':
        if fields.get('reason') not in Request.Reason.values:
            raise Refused('reason', 'invalid')
        code, words = _declined_letter(request, fields['reason'], timezone.localdate())
    else:
        raise Refused('act', 'invalid')
    return accesses.letter(request.user, code, **words)


def _tell_staff(request: Request, what: str) -> None:
    """A plain letter to ACCESS_LETTER_TO: a request arrived, or its account answered the line asked. Nothing is sent
    when the setting is empty."""
    to = settings.ACCESS_LETTER_TO
    if not to:
        return
    user = request.user
    asks = _granted_words(request.wants_api, request.wants_data)
    change = request.change_of_id is not None
    kind = 'a request to change an access' if change else 'a request for access'
    head = (f'{kind.capitalize()} arrived from {request.name}.' if what == 'arrived'
            else f'{request.name} answered what you asked.')
    lines = [
        head,
        '',
        f'Who: {request.name}, {request.get_kind_display().lower()}; account {user.username}, '
        f'{(timezone.now() - user.date_joined).days} days old, address {"proven" if user.email_proven_at else "not proven"}',
        f'What for: {request.purpose}',
    ]
    if change:
        held = request.change_of
        lines += [f'Holds now: {_granted_words(held.api, held.data)}; size {held.size}',
                  f'Asks to hold: {asks}; size {request.wanted_size or "as it is"}']
    else:
        lines += [f'Asks for: {asks}; volume {request.get_volume_display().lower()}; '
                  f'{"commercial" if request.commercial else "not commercial"}']
    lines.append(f'Runs at: {request.runs_at or "not said"}')
    if what == 'answered':
        lines += ['', f'You asked: {request.asked}', f'The answer: {request.answer}']
    site = settings.SITE_URL.rstrip('/')
    link = site + reverse('admin:opendata_request_change', args=[request.pk])
    lines += ['', f'Answer it on the desk: {site}/data/desk', f'Or here: {link}']
    subject = (f'{settings.SITE_NAME}: {kind} from {request.name}' if what == 'arrived'
               else f'{settings.SITE_NAME}: {request.name} answered your question')
    mail.plain(to, subject, '\n'.join(lines) + '\n')


def _granted_words(api: bool, data: bool) -> str:
    return ' and '.join(w for w, on in (('the API', api), ('the database', data)) if on) or 'nothing'


def counted(today: date | None = None) -> dict:
    """The queue's figures, in QUERIES queries: requests received, accepted and declined in the last WINDOW_DAYS days
    with the median days to an answer; how many wait for the staff and since how many days the oldest has waited (since
    it was sent, or since its account answered what was asked); the accesses that end within WINDOW_DAYS days."""
    today = today or timezone.localdate()
    now = timezone.now()
    since = now - timedelta(days=WINDOW_DAYS)
    decided = Q(state__in=(Request.State.ACCEPTED, Request.State.DECLINED), decided_at__gte=since)
    figures = Request.objects.aggregate(
        received=Count('pk', filter=Q(created_at__gte=since)),
        accepted=Count('pk', filter=decided & Q(state=Request.State.ACCEPTED)),
        declined=Count('pk', filter=decided & Q(state=Request.State.DECLINED)),
        waiting=Count('pk', filter=Q(state=Request.State.WAITING)),
        oldest=Min('waiting_since', filter=Q(state=Request.State.WAITING)))
    spans = [(d - c).total_seconds() / 86400
             for c, d in Request.objects.filter(decided).values_list('created_at', 'decided_at')]
    oldest = figures.pop('oldest')
    figures['median_days'] = round(statistics.median(spans), 1) if spans else None
    figures['oldest_days'] = (now - oldest).days if oldest else None
    figures['ending'] = Access.objects.filter(state=Access.State.LIVE, ends_on__gte=today,
                                              ends_on__lte=today + timedelta(days=WINDOW_DAYS)).count()
    return figures


def lines(f: dict) -> list[str]:
    """The figures in two lines of plain English."""
    median = (f'a median of {f["median_days"]:g} days to an answer' if f['median_days'] is not None
              else 'none answered')
    waiting = (f'{f["waiting"]:,}, the oldest for {f["oldest_days"]:,} days' if f['waiting'] else 'none')
    return [f'Access requests, the last {WINDOW_DAYS} days: {f["received"]:,} received, {f["accepted"]:,} accepted, '
            f'{f["declined"]:,} declined; {median}.',
            f'Waiting for an answer: {waiting}. Accesses ending within {WINDOW_DAYS} days: {f["ending"]:,}.']


def _start_of(d: date) -> datetime:
    return timezone.make_aware(datetime.combine(d, time.min))


def _what(e: Event) -> str:
    """What a decision did, in a few plain words, from its details."""
    d = e.details
    if e.act == Event.Act.ACCEPTED:
        held = f'{_granted_words(d.get("api"), d.get("data"))}, size {d.get("size")}'
        return f'{held}, until {d.get("ends_on")}' if d.get('ends_on') else held
    if e.act == Event.Act.ASKED:
        return f'asked «{d.get("line", "")}»'
    if e.act == Event.Act.CHANGED:
        before, after = d.get('before', {}), d.get('after', {})
        return (f'from {_granted_words(before.get("api"), before.get("data"))}, size {before.get("size")} '
                f'to {_granted_words(after.get("api"), after.get("data"))}, size {after.get("size")}')
    if e.act == Event.Act.RENEWED:
        return f'until {d.get("ends_on")}'
    if e.act == Event.Act.KEY_ENDED:
        return f'key {d.get("key")}'
    return str(d.get('reason', ''))                        # declined, ended


VERBS = {Event.Act.ACCEPTED: 'accepted', Event.Act.ASKED: 'asked for more of', Event.Act.DECLINED: 'declined',
         Event.Act.CHANGED: 'changed the access of', Event.Act.RENEWED: 'renewed the access of',
         Event.Act.ENDED: 'ended the access of', Event.Act.KEY_ENDED: 'ended a key of'}


def decisions(first: date, last: date) -> list[str]:
    """The staff's decisions from day `first` to day `last` (Morocco's), oldest first, one plain line each: who
    decided, what, for whom; DECISIONS_SHOWN at most, then «and N more»; none, no line. A holder's own acts and the
    night's job are not decisions. DECISION_QUERIES queries."""
    # A holder's own acts are left out; an event names a request, an access or both, and the side it does not name
    # must leave nothing out (a comparison with nothing is no answer in SQL, and would).
    own = (Q(request__isnull=False, by=F('request__user')) | Q(access__isnull=False, by=F('access__user')))
    rows = (Event.objects.filter(act__in=DECIDED, at__gte=_start_of(first), at__lt=_start_of(last + timedelta(days=1)))
            .exclude(by=None).exclude(own))
    shown = list(rows.select_related('by', 'request__user', 'access__user', 'access__request')
                 .order_by('at', 'pk')[:DECISIONS_SHOWN])
    total = rows.count()
    out = []
    for e in shown:
        asked_by = e.request or (e.access.request if e.access else None)
        user = e.request.user if e.request else e.access.user if e.access else None
        whom = f'{asked_by.name or "(no name)"} ({user.username})' if asked_by and user else 'a deleted row'
        reason = f' ({_what(e)})' if e.act in (Event.Act.DECLINED, Event.Act.ENDED) else ''
        what = '' if reason else f': {_what(e)}'
        out.append(f'- {e.by.username} {VERBS[e.act]} {whom}{reason}{what}.')
    if total > len(shown):
        out.append(f'- and {total - len(shown):,} more.')
    return out


def forget_typed(today: date | None = None) -> int:
    """The retention /privacy states: the typed answers of a request declined DECLINED_MONTHS ago, and of the request
    behind an access ended ENDED_MONTHS ago (and of the requests to change it), are emptied. Their states, dates and
    codes stay. Three writes."""
    today = today or timezone.localdate()
    declined = _start_of(accesses.months_after(today, -DECLINED_MONTHS))
    ended = _start_of(accesses.months_after(today, -ENDED_MONTHS))
    rows = Request.objects.exclude(**accesses.TYPED)
    return (rows.filter(state=Request.State.DECLINED, decided_at__lt=declined).update(**accesses.TYPED)
            + rows.filter(access__state=Access.State.ENDED, access__ended_at__lt=ended).update(**accesses.TYPED)
            + rows.filter(change_of__state=Access.State.ENDED, change_of__ended_at__lt=ended).update(**accesses.TYPED))
