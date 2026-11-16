"""The moderators' desk and its jobs cost the same for a few rows as for ten times as many (no query inside a loop): the
appeals and pauses tabs and their counts, the thanks a kept contribution's reporters get, the reviewers' digest. Each
answers what the row-by-row code answered: the tabs hold the rows `_may_decide_appeal` and `covers` let through."""
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.discussion.models import Appeal, Ban, Contribution, Discussion, Notice, Report
from apps.discussion.services import places, review
from apps.discussion.services.review.reviewers import _may_decide_appeal, covers
from apps.discussion.tests.conftest import lease, make_user, signed_in, uploads  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db
HOUSING, WORK = '/talk/housing', '/talk/work'


@pytest.fixture
def desk(lease):
    """Staff, a moderator of the housing topic only, and another staff member who removes and pauses too."""
    staff = make_user('staff', staff=True)
    mod = make_user('mod')
    review.appoint(staff, mod, [HOUSING])
    make_user('boss', staff=True)
    for path in (HOUSING, WORK):
        Discussion.objects.create(path=path, text_path=path)
    return staff, mod


def appeals(desk, start: int, end: int):
    """Rows `start` to `end`: in turn in the housing and the work topics, a removed contribution appealed, a pause
    appealed (every fourth one through no contribution), a pause with no appeal; the removals and pauses in turn the
    moderator's, the other staff member's and staff's own acts, every fifth appeal the moderator's own."""
    staff, mod = desk
    boss = User.objects.get(username='boss')
    places = {d.path: d for d in Discussion.objects.all()}
    for i in range(start, end):
        d = places[HOUSING if i % 2 else WORK]
        author = mod if i % 5 == 0 else make_user(f'w{i}')
        by = (mod if author != mod else boss, boss, staff)[i % 3]
        removed = Contribution.objects.create(discussion=d, author=author, kind='post', title=f'منشور {i}',
                                              body=f'كلام {i}', removed_at=timezone.now(), removed_by=by,
                                              removed_rule='respect')
        Appeal.objects.create(user=author, contribution=removed, text='ما خرقت حتى قاعدة')
        via = Contribution.objects.create(discussion=d, author=author, kind='comment', body=f'تعليق {i}',
                                          anonymous=i % 7 == 0)
        ban = Ban.objects.create(user=author, rule='respect', by=by, via=via if i % 4 else None,
                                 until=timezone.now() + timedelta(days=3))
        Appeal.objects.create(user=author, ban=ban, text='الإيقاف طويل')
        Ban.objects.create(user=make_user(f'p{i}'), rule='respect', by=staff, via=via, until=timezone.now() + timedelta(days=7))


def by_hand(user, tab: str) -> list[int]:
    """The tab as it was read before: every open row loaded, then let through one by one."""
    if tab == 'appeals':
        rows = Appeal.objects.filter(decided_at=None).order_by('created_at')
        return [a.pk for a in rows if _may_decide_appeal(user, a)]
    rows = Ban.objects.filter(ended_at=None).order_by('-started_at')
    return [b.pk for b in rows if user.is_staff or (b.via and covers(user, b.via.discussion.text_path))]


def asked(call) -> tuple[int, object]:
    with CaptureQueriesContext(connection) as queries:
        out = call()
    return len(queries), out


@pytest.mark.parametrize('tab', ['appeals', 'pauses'])
def test_the_appeals_and_pauses_tabs_cost_the_same_whatever_waits(api, desk, tab):
    staff, mod = desk
    costs = []
    for start, end in ((0, 3), (3, 30)):
        appeals(desk, start, end)
        for user in (staff, mod):
            n, r = asked(lambda: signed_in(api, user).get('/api/discussion/review/', {'tab': tab}))  # noqa: B023 (called in this iteration)
            assert r.status_code == 200
            got = r.json()
            assert [i['id'] for i in got['items']] == by_hand(user, tab)
            assert got['counts'][tab] == len(by_hand(user, tab))
            costs.append(n)
    assert costs[:2] == costs[2:], costs


def test_an_appeal_on_a_pause_shows_the_contribution_it_came_through(api, desk):
    _staff, mod = desk
    appeals(desk, 0, 8)
    items = signed_in(api, mod).get('/api/discussion/review/', {'tab': 'appeals'}).json()['items']
    pauses = [i for i in items if i['on'] == 'pause']
    assert pauses and all(i['contribution']['path'].startswith(f'{HOUSING}/') for i in pauses)
    assert all(i['pause']['rule'] == 'respect' for i in pauses)


def reported(desk, start: int, end: int) -> Contribution:
    """The housing topic's one post, reported by readers `start` to `end`; every third one already told of it."""
    d = Discussion.objects.get(path=HOUSING)
    c = Contribution.objects.filter(discussion=d, title='منشور مبلغ عنه').first() or Contribution.objects.create(
        discussion=d, author=make_user('author'), kind='post', title='منشور مبلغ عنه', body='كلام')
    for i in range(start, end):
        reader = make_user(f'r{i}')
        Report.objects.create(contribution=c, reporter=reader, reason='abuse')
        if i % 3 == 0:
            Notice.objects.create(user=reader, kind=Notice.Kind.REPORT, contribution=c, detail='reviewed')
    return c


def told(c) -> list[tuple]:
    return sorted(Notice.objects.filter(kind=Notice.Kind.REPORT, contribution=c)
                  .values_list('user__username', 'detail', 'path', 'emailed_at', 'letter_due'))


@pytest.mark.parametrize('act', ['keep', 'remove'])
def test_a_contributions_reporters_are_thanked_once_whatever_their_number(desk, act):
    staff, _ = desk
    costs = []
    for start, end in ((0, 3), (3, 30)):
        c = reported(desk, start, end)
        Contribution.objects.filter(pk=c.pk).update(removed_at=None, removed_by=None, removed_rule='')
        n, _ = asked(lambda: review.keep(staff, c.pk) if act == 'keep' else review.remove(staff, c.pk, 'respect'))  # noqa: B023 (called in this iteration)
        costs.append(n)
        where = places.notice_path(c)
        expected = [(f'r{i}', 'reviewed' if i % 3 == 0 or act == 'keep' else 'acted', '' if i % 3 == 0 else where,
                     None, False) for i in range(end)]
        assert told(c) == sorted(expected)
    assert costs[0] == costs[1], costs


def waiting(desk, start: int, end: int):
    """Moderators `start` to `end` (of the housing topic, of everything, of the work topic, in turn; every fourth told
    today already), and as many contributions waiting in turn in the two topics: held thirteen hours, held an hour,
    reported thirteen hours ago."""
    staff, _ = desk
    places = {d.path: d for d in Discussion.objects.all()}
    for i in range(start, end):
        mod = make_user(f'm{i}')
        area = ([HOUSING], [], [WORK])[i % 3]
        review.appoint(staff, mod, area, everywhere=not area)
        if i % 4 == 0:
            Notice.objects.create(user=mod, kind=Notice.Kind.DIGEST, detail='0', emailed_at=timezone.now())
        d = places[HOUSING if i % 2 else WORK]
        age = timedelta(hours=(13, 1, 13)[i % 3])
        c = Contribution.objects.create(discussion=d, author=make_user(f'a{i}'), kind='post', title=f'منشور {i}',
                                        body=f'كلام {i}', held_at=timezone.now() - age if i % 3 < 2 else None,
                                        post_review_at=timezone.now() - age if i % 3 == 2 else None)
        if i % 3 == 2:
            for j in range(2):
                Report.objects.create(contribution=c, reporter=make_user(f'r{i}-{j}'), reason='abuse')


def digests() -> list[tuple]:
    from django.core import mail
    told = sorted(Notice.objects.filter(kind=Notice.Kind.DIGEST, created_at__gte=timezone.now() - timedelta(minutes=5))
                  .exclude(detail='0').values_list('user__username', 'detail'))
    return told, sorted((m.to[0], m.body.split('\n')[0]) for m in mail.outbox)


def test_the_reviewers_digest_costs_the_same_whatever_its_reviewers_and_queue(desk):
    import io

    from django.core import mail
    costs, seen = [], []
    for start, end in ((0, 3), (3, 30)):
        waiting(desk, start, end)
        Notice.objects.filter(kind=Notice.Kind.DIGEST).exclude(detail='0').delete()
        mail.outbox.clear()
        n, _ = asked(lambda: call_command('review_digest', stdout=io.StringIO()))
        costs.append(n)
        seen.append(digests())
    told, letters = seen[1]
    assert len(told) == len(letters) > 20
    # Twenty held and ten reported everywhere; fifteen in each topic. m0 and m4 were told today already.
    assert {k: dict(told).get(k) for k in ('staff', 'm1', 'm3', 'm2', 'm0', 'm4')} == {
        'staff': '30', 'm1': '30', 'm3': '15', 'm2': '15', 'm0': None, 'm4': None}
    assert costs[0] == costs[1], costs


def due(lease, start: int, end: int):
    """Letters `start` to `end` claimed: in turn an answer on an article's thread (each its own article), a new
    comment under a post of the housing topic (each its own post, every third one held, so its title is said only to
    its author), and a removal of a post's words, which its author is told of whatever its state."""
    from apps.corpus.models import Article
    from apps.discussion.services import anchors

    version = lease.latest_version()
    housing = Discussion.objects.get(path=HOUSING)
    for i in range(start, end):
        person = make_user(f'l{i}')
        if i % 3 == 0:
            Article.objects.create(version=version, order=200 + i, label=f'المادة {200 + i}', number=str(200 + i),
                                   eid=f'art_{200 + i}', body=f'نص {i}.')
            path = f'/ma/loi/2013/67-12/art_{200 + i}'
            d = Discussion.objects.create(path=path, text_path='/ma/loi/2013/67-12')
            c = Contribution.objects.create(discussion=d, author=make_user(f'x{i}'), kind='comment', body=f'جواب {i}')
            Notice.objects.create(user=person, kind=Notice.Kind.ANSWER, contribution=c, path=anchors.find(path).path,
                                  letter_due=True)
            continue
        post = Contribution.objects.create(discussion=housing, author=person if i % 3 == 2 else make_user(f'y{i}'),
                                           kind='post', title=f'عنوان {i}', body=f'منشور {i}',
                                           held_at=timezone.now() if i % 2 else None)
        kind = Notice.Kind.REMOVED if i % 3 == 2 else Notice.Kind.NEW
        Notice.objects.create(user=person, kind=kind, contribution=post, path=places.post_path(post), letter_due=True,
                              detail='respect' if kind == Notice.Kind.REMOVED else '')


def test_the_notice_letters_cost_the_same_whatever_their_number(lease, desk):
    from django.core import mail

    from apps.discussion.services import notices
    costs, letters = [], []
    for start, end in ((0, 3), (3, 30)):
        due(lease, start, end)
        mail.outbox.clear()
        n, (claimed, sent) = asked(notices.send_due)
        assert claimed == sent == end - start
        costs.append(n)
        letters.append(sorted((m.to[0], m.body.split('\n')[0]) for m in mail.outbox))
    said = dict(letters[1])
    # An article by its name; a held post's title to its author alone.
    assert 'المادة 203 — قانون الكراء' in said['l3@example.org'] and 'عنوان 5 — السكن والكراء' in said['l5@example.org']
    assert 'عنوان' not in said['l7@example.org'] and 'عنوان 4' in said['l4@example.org']
    assert costs[0] == costs[1], costs


def due_for_erasing(start: int, end: int):
    """Contributions `start` to `end`: in turn removed 91 days ago and deleted after a report since decided, each with
    a voice, two pictures, an earlier wording and a citation; and a voice and a picture left as drafts two days ago."""
    from apps.discussion.models import Cite, Revision
    from apps.media.models import Clip, Picture

    d = Discussion.objects.get(path=HOUSING)
    long_ago = timezone.now() - timedelta(days=91)
    for i in range(start, end):
        author = make_user(f'e{i}')
        clip = Clip.objects.create(owner=author, duration_ms=1000, size=10, file_name=f'v{i}.m4a', state='evidence')
        pictures = [Picture.objects.create(owner=author, full_name=f'p{i}-{k}.webp', thumb_name=f't{i}-{k}.webp',
                                           width=10, height=10, state='evidence') for k in (0, 1)]
        c = Contribution.objects.create(discussion=d, author=author, kind='post', title=f'منشور {i}', body=f'كلام {i}',
                                        clip=clip, removed_at=long_ago if i % 2 else None,
                                        deleted_at=None if i % 2 else long_ago)
        c.pictures.set(pictures)
        Revision.objects.create(contribution=c, body=f'كلام أول {i}')
        Cite.objects.create(contribution=c, path='/ma/loi/2013/67-12/art_34', text_path='/ma/loi/2013/67-12')
        if not i % 2:
            Report.objects.create(contribution=c, reporter=make_user(f'q{i}'), reason='abuse', status='reviewed',
                                  decided_at=timezone.now())
        Clip.objects.create(owner=author, duration_ms=1000, size=10, file_name=f'd{i}.m4a')
        Picture.objects.create(owner=author, full_name=f'dp{i}.webp', thumb_name=f'dt{i}.webp', width=10, height=10)
    Clip.objects.filter(state='draft').update(created_at=timezone.now() - timedelta(days=2))
    Picture.objects.filter(state='draft').update(created_at=timezone.now() - timedelta(days=2))


def erased() -> tuple:
    from apps.discussion.models import Cite, Revision
    from apps.media.models import Clip, Picture
    return (sorted(Contribution.objects.filter(erased_at__isnull=False).values_list('title', 'body', 'quote', 'links',
                                                                                  'held_spans')),
            sorted(Clip.objects.values_list('file_name', 'state', Q_erased('erased_at'))),
            sorted(Picture.objects.values_list('full_name', 'thumb_name', 'state', Q_erased('erased_at'))),
            Revision.objects.count(), Cite.objects.count())


def Q_erased(field):
    from django.db.models import BooleanField, ExpressionWrapper, Q
    return ExpressionWrapper(Q(**{f'{field}__isnull': False}), output_field=BooleanField())


def test_what_the_rules_promise_is_erased_at_one_cost(desk, django_capture_on_commit_callbacks):
    import io
    costs, outs = [], []
    for start, end in ((0, 4), (4, 40)):
        due_for_erasing(start, end)
        out = io.StringIO()
        with django_capture_on_commit_callbacks(execute=True):
            n, _ = asked(lambda: call_command('keep_promises', stdout=out))  # noqa: B023 (called in this iteration)
        costs.append(n)
        outs.append(out.getvalue())
    words, clips, pictures, revisions, cites = erased()
    assert len(words) == 40 and all(w == ('', '', '', [], []) for w in words) and revisions == cites == 0
    assert set(clips) == {('', 'erased', True)} and len(clips) == 80
    assert set(pictures) == {('', '', 'erased', True)} and len(pictures) == 120
    assert outs[1].startswith('drafts 72, contributions erased 36,')
    assert costs[0] == costs[1], costs


def test_erasing_renews_the_discussions_kept_answers(desk, monkeypatch, django_capture_on_commit_callbacks):
    """Each row's save renewed them (apps.discussion.apps); erased together, they are renewed still."""
    import io

    from apps.corpus.services import generation
    due_for_erasing(0, 2)
    renewed = []
    monkeypatch.setattr(generation, 'bump', lambda *scopes: renewed.append(scopes))
    with django_capture_on_commit_callbacks(execute=True):
        call_command('keep_promises', stdout=io.StringIO())
    assert renewed and all(scopes == ('talk',) for scopes in renewed)
