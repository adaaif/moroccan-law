"""What people are told, on their account page and, for some, by email: an answer, something new where they
follow, a decision about their words. One email per discussion every six hours at most: a busy thread is one letter,
not twenty.

A notice is written in the request that makes it; its letter is only claimed there (`letter_due`) and sent by the job
`send_notice_letters` (deploy/law-letters.timer): a call to the mail provider can take seconds, and a topic with a
thousand followers held the writer's request for a thousand of them. A post's followers are told in one insert."""
import time
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.accounts.services import mail
from apps.accounts.services.refusals import Refused
from apps.discussion.models import Contribution, Follow, Notice, Rule
from apps.discussion.services import holds

EMAILED = {Notice.Kind.ANSWER: 'answer', Notice.Kind.NEW: 'new', Notice.Kind.REMOVED: 'removed',
           Notice.Kind.APPROVED: 'approved', Notice.Kind.SENT_BACK: 'sent_back',
           Notice.Kind.REDACTED: 'redacted'}
# Decisions about one's own words are always sent; the rest at most one a discussion every six hours.
ALWAYS = {Notice.Kind.REMOVED, Notice.Kind.APPROVED, Notice.Kind.SENT_BACK, Notice.Kind.REDACTED}
EMAIL_GAP = timedelta(hours=6)


def label(path: str, viewer_id: int | None = None) -> str:
    """An address in words for a letter or the stop page; a post's title only while readers may read it, or for its
    own author (`viewer_id`)."""
    from apps.discussion.services import anchors, places
    if path.startswith(places.PREFIX):
        found = places.label(path, viewer_id)
        return ' — '.join(x for x in (found['title'], (found['name'] or {}).get('ar', '')) if x) or path
    try:
        a = anchors.find(path)
    except Exception:  # noqa: BLE001 — a letter must not fail for its label
        return path
    from apps.corpus.services.codes import display_name
    return f'{a.article.label} — {display_name(a.text)["ar"]}'


def labels(keys) -> dict[tuple, str]:
    """`label` for many (address, viewer) pairs, in a fixed number of queries whatever their number: the articles
    through one `anchors.find_many`, the posts' titles in one query for what readers may read and one for their
    authors' own (one `label` an address before: three queries an article)."""
    from apps.corpus.services.codes import display_name
    from apps.discussion.services import anchors, counters, places

    keys = list(dict.fromkeys(keys))
    posts = {key: places.split_post(key[0]) for key in keys if key[0].startswith(places.PREFIX)}
    found = anchors.find_many([path for path, _ in keys if (path, _) not in posts])
    pks = {pk for _, pk in posts.values() if pk}
    shown = dict(Contribution.objects.filter(counters.published(), pk__in=pks).values_list('pk', 'title')) if pks else {}
    asked = {pk for (_, viewer), (_, pk) in posts.items() if pk and viewer}
    own = {pk: (author, title) for pk, author, title in
           Contribution.objects.filter(pk__in=asked).values_list('pk', 'author_id', 'title')} if asked else {}
    out = {}
    for key in keys:
        path, viewer = key
        if key in posts:
            place_path, pk = posts[key]
            try:
                place = places.find(place_path)
            except Refused:
                out[key] = path
                continue
            title = shown.get(pk) or (own[pk][1] if pk in own and own[pk][0] == viewer else '') if pk else ''
            out[key] = ' — '.join(x for x in (title or '', (place.name or {}).get('ar', '')) if x) or path
        else:
            a = found.get(path)
            out[key] = f'{a.article.label} — {display_name(a.text)["ar"]}' if a is not None else path
    return out


def link(path: str, contribution: Contribution | None = None) -> str:
    """Where a letter leads: a post's own page, or an article's discussion as before."""
    where = path if path.startswith('/talk/') else f'/discussion{path}'
    return f'{settings.SITE_URL}{where}' + (f'#c{contribution.pk}' if contribution else '')


def _takes_letters(user) -> bool:
    return bool(user.email_notices and user.email_proven_at and not user.deleted_at)


def notify(user, kind: str, *, contribution: Contribution | None = None, path: str = '', detail: str = '') -> Notice:
    """The notice, and its letter claimed for the job when the person takes letters and this discussion sent none in
    the last six hours (decisions about one's own words always)."""
    due = False
    if kind in EMAILED and _takes_letters(user):
        recent = Notice.objects.filter(user=user, path=path, emailed_at__gte=timezone.now() - EMAIL_GAP)
        due = kind in ALWAYS or not (path and recent.exists())
    return Notice.objects.create(user=user, kind=kind, contribution=contribution, path=path, detail=detail,
                                 emailed_at=timezone.now() if due else None, letter_due=due)


def _tell_many(users: list, kind: str, contribution: Contribution, path: str, details: dict | None = None) -> None:
    """The same notice to many people in one insert, their letters claimed as `notify` claims one: the six hours
    since each one's last letter about this discussion read in one query. `details`: each person's own detail, by
    their key."""
    if not users:
        return
    now = timezone.now()
    lettered = set()
    if kind in EMAILED:
        takers = [u.pk for u in users if _takes_letters(u)]
        recent = set(Notice.objects.filter(user_id__in=takers, path=path, emailed_at__gte=now - EMAIL_GAP)
                     .values_list('user_id', flat=True)) if path and takers else set()
        lettered = {pk for pk in takers if pk not in recent}
    Notice.objects.bulk_create([Notice(user=u, kind=kind, contribution=contribution, path=path,
                                       detail=(details or {}).get(u.pk, ''),
                                       emailed_at=now if u.pk in lettered else None, letter_due=u.pk in lettered)
                                for u in users])


def on_published(c: Contribution) -> None:
    """A contribution readers can now see: its parent's author is told, then whoever follows the post (a comment) or
    the topic (a new post); an article thread's followers as before."""
    from apps.discussion.services import places

    path = places.post_path(c) if places.is_place(c.discussion.path) else c.discussion.path
    told = {c.author_id}
    if c.parent_id and c.parent.author_id not in told:
        notify(c.parent.author, Notice.Kind.ANSWER, contribution=c, path=path)
        told.add(c.parent.author_id)
    # A post's followers hear of its comments under the post; a topic's of its new posts under the topic, one line.
    followed = [path] + ([c.discussion.path] if c.parent_id is None and path != c.discussion.path else [])
    by_path: dict[str, list] = {p: [] for p in followed}
    # The post's followers first: one following both hears once, under the post.
    rows = Follow.objects.filter(path__in=followed).exclude(user_id__in=told).select_related('user')
    for follow in sorted(rows, key=lambda f: followed.index(f.path)):
        if follow.user_id not in told:
            told.add(follow.user_id)
            by_path[follow.path].append(follow.user)
    for where, users in by_path.items():
        _tell_many(users, Notice.Kind.NEW, c, where)


# A letter the job finds later than this is not sent: news a day old is on the account page, not in an inbox.
LETTER_LATE = timedelta(days=1)
LETTERS_A_RUN = 500


def send_due(most: int = LETTERS_A_RUN) -> tuple[int, int]:
    """The letters claimed and not sent yet, oldest first, each once (claimed before it goes: a run that dies midway
    loses a letter rather than sending it twice), NOTICE_LETTER_PACE_S apart: the mail provider takes a few a second.
    Returns how many were claimed and how many the mail service took."""
    now = timezone.now()
    Notice.objects.filter(letter_due=True, created_at__lt=now - LETTER_LATE).update(letter_due=False)
    due = list(Notice.objects.filter(letter_due=True).select_related('user', 'contribution').order_by('created_at')[:most])
    if not due:
        return 0, 0
    Notice.objects.filter(pk__in=[n.pk for n in due]).update(letter_due=False)
    # A post's title, once a path: shown to its own author also while it cannot be read (a decision about it). Every
    # letter's label read at once.
    going = [n for n in due if EMAILED.get(n.kind) is not None and _takes_letters(n.user)]
    said = labels((n.path, n.user.pk if n.kind in ALWAYS else None) for n in going if n.path)
    sent = 0
    for n in going:
        user, letter = n.user, EMAILED[n.kind]
        key = (n.path, user.pk if n.kind in ALWAYS else None)
        words = {'label': said.get(key, ''), 'link': link(n.path, n.contribution),
                 'rule': list(Rule.values).index(n.detail) + 1 if n.detail in Rule.values else '',
                 'note': n.contribution.review_note if n.contribution is not None else ''}
        if sent and settings.NOTICE_LETTER_PACE_S:
            time.sleep(settings.NOTICE_LETTER_PACE_S)
        sent += mail.send(user, letter, path=n.path, **words)
    return len(due), sent


def grouped(user, limit: int = 40) -> list[dict]:
    """What the account page lists (R2): one line per discussion for what is new where one follows («3 مساهمات
    جديدة»), the rest one by one, newest first; who answered, unless they wrote without a name."""
    out: list[dict] = []
    news: dict[str, dict] = {}
    rows = (Notice.objects.filter(user=user).select_related('contribution__author').order_by('-created_at')[:300])
    for n in rows:
        if n.kind == Notice.Kind.NEW and n.path:
            group = news.get(n.path)
            if group is None:
                group = news[n.path] = {'id': n.pk, 'kind': n.kind, 'path': n.path, 'contribution': n.contribution_id,
                                        'detail': n.detail, 'created_at': n.created_at, 'seen': True, 'count': 0,
                                        'who': None}
                out.append(group)
            group['count'] += 1
            group['seen'] = group['seen'] and bool(n.seen_at)
            continue
        c = n.contribution
        who = None
        # Who answered, while the answer can be read: a held or removed answer names nobody.
        if (n.kind == Notice.Kind.ANSWER and c is not None and not c.anonymous and not c.author.deleted_at
                and c.published):
            who = holds.shown_name(c.author)
        out.append({'id': n.pk, 'kind': n.kind, 'path': n.path, 'contribution': n.contribution_id, 'detail': n.detail,
                    'created_at': n.created_at, 'seen': bool(n.seen_at), 'count': 1, 'who': who})
        if len(out) >= limit:
            break
    return out[:limit]


def stop(token: str, scope: str) -> dict:
    """A letter's stop link (R3): this discussion's letters, or all of them. No sign-in: the signed token is the
    proof."""
    from apps.accounts.models import User

    found = mail.read_stop(token)
    user = User.objects.filter(pk=found[0]).first() if found else None
    if user is None:
        raise Refused('token', 'invalid')
    path = found[1]
    if scope == 'all' or not path:
        user.email_notices = False
        user.save(update_fields=['email_notices'])
    else:
        Follow.objects.filter(user=user, path=path).delete()
    return {'scope': 'all' if scope == 'all' or not path else 'path', 'path': path,
            'label': label(path, user.pk) if path else ''}


def follow(user, path: str) -> None:
    """Follow a topic's place (/talk/family) or a post (/talk/family/12) the caller may open: following by number
    told the title of a held or removed post to whoever walked the numbers."""
    from apps.discussion.services import gates, places, thread

    gates.voter(user)
    place, pk = places.split_post(path)
    found = places.find(place)
    if pk and not thread.may_open(user, pk, found.path):
        raise Refused('path', 'not_found', 404)
    Follow.objects.get_or_create(user=user, path=f'{found.path}/{pk}' if pk else found.path)
