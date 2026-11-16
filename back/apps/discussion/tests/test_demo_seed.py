"""The development's demo (seed_demo_talk, then demo_cases): its people, the posts and every state a moderator meets,
written through the services with the check off; what a run before left (the demo's, the end-to-end runs') is taken
away first; a database without DEBUG is refused. One run: it writes about two hundred contributions."""
from datetime import date, datetime, timedelta, UTC

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Count, Max, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.services.addresses import split_path
from apps.discussion.management.commands import demo_cases, demo_content as words, seed_demo_talk as seed
from apps.discussion.models import (Action, Appeal, Ban, Check, Contribution, Discussion, Follow, Notice, Point,
                                    Reviewer, Revision, Trust, Useful)
from apps.discussion.services import places
from apps.discussion.tests.conftest import make_user

pytestmark = pytest.mark.django_db

MOMENT = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
PASSWORD = 'a demo pass 2026'


def the_articles_the_demo_starts_from():
    """Each article a demo post starts from or quotes, with the quoted words in its body."""
    quoted = {seed.ART_49: list(words.ART49_QUOTES), demo_cases.THREAD['about']: []}
    for path, small in words.SMALL.items():
        quoted.setdefault(path, []).extend(small['quotes'])
    for *_, about, quote in seed.HOUSING_POSTS + seed.WORK_POSTS:
        if about:
            quoted.setdefault(about, []).append(quote)
    for p in demo_cases.POSTS:
        if p.get('about'):
            quoted.setdefault(p['about'], []).append(p.get('quote', ''))
    versions = {}
    for k, (path, quotes) in enumerate(quoted.items()):
        uri, eid = split_path(path)
        if uri not in versions:
            text = Text.objects.create(akn_uri=uri, type='law', number=uri.rsplit('/', 1)[-1], title_ar='نص')
            versions[uri] = Version.objects.create(text=text, language='ar', valid_from=date(2020, 1, 1),
                                                   consolidation=Consolidation.AS_PUBLISHED)
        Article.objects.create(version=versions[uri], order=k, label='المادة', number=eid[4:], eid=eid,
                               body=' . '.join(['نص المادة', *quotes]))


def test_the_demo_goes_on_a_development_database_only(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match='development database only'):
        call_command('seed_demo_talk')
    assert not User.objects.exists() and not Contribution.objects.exists()


def test_the_demo_writes_its_people_and_every_state_a_moderator_meets_and_replaces_what_a_run_before_left(
        settings, monkeypatch, capsys):
    settings.DEBUG = True
    monkeypatch.setenv('DEMO_PASSWORD', PASSWORD)
    monkeypatch.setattr(timezone, 'now', lambda: MOMENT)
    the_articles_the_demo_starts_from()
    # What a run before left: a demo account and an end-to-end run's, with a row in every table the demo clears.
    staff = make_user('staff', staff=True)
    reader = make_user('reader')
    old = User.objects.create_user('demo-old', 'demo-old@example.org', 'x' * 12)
    e2e = User.objects.create_user('e2e-run', 'run@demo.law.invalid', 'x' * 12)
    tester = User.objects.create_user('demo-tester', 'demo-tester@demo.law.invalid', 'x' * 12, is_active=False)
    work, _ = Discussion.objects.get_or_create(path='/talk/work', defaults={'text_path': '/talk/work'})
    general = Discussion.objects.create(path='/talk/general', text_path='/talk/general', locked_at=MOMENT, locked_by=old)
    gone = [Contribution.objects.create(discussion=work, author=who, kind='post', title='قديم', body='قديم')
            for who in (old, e2e)]
    kept = [Contribution.objects.create(discussion=work, author=reader, kind='post', title='باقي', body='باقي')
            for _ in range(3)]
    rows = {}
    for who, appealed in zip((old, e2e, reader), kept):
        rows[who.username] = [
            Point.objects.create(user=who, source='useful', ref=f'old-{who.pk}', amount=1),
            Check.objects.create(user=who, outcome='publish'),
            Appeal.objects.create(user=who, contribution=appealed, text='طعن'),
            Ban.objects.create(user=who, rule='respect', until=MOMENT), Trust.objects.create(user=who),
            Notice.objects.create(user=who, kind='approved'), Follow.objects.create(user=who, path='/talk/work'),
            Reviewer.objects.create(user=who, text_paths=['/talk/work']), Action.objects.create(actor=who, verb='approve')]
    Action.objects.create(actor=staff, verb='pause', target=old)

    call_command('seed_demo_talk')

    out = capsys.readouterr().out
    demo = User.objects.filter(username__startswith='demo-')
    # The run before: its rows gone, a real reader's kept, the lock it left lifted.
    assert not Contribution.objects.filter(pk__in=[c.pk for c in gone]).exists()
    assert Contribution.objects.filter(pk__in=[c.pk for c in kept]).count() == 3
    for row in rows['demo-old'] + rows['e2e-run']:
        assert not type(row).objects.filter(pk=row.pk).exists(), row
    assert all(type(row).objects.filter(pk=row.pk).exists() for row in rows['reader'])
    assert not Action.objects.filter(target=old).exists()
    general.refresh_from_db()
    assert (general.locked_at, general.locked_by) == (None, None)

    # The people: every demo account opens with the one password; the tester, the newcomer and the unproven differ.
    assert demo.count() == len(words.PEOPLE) + 5           # with the staff, tester, new, unproven and the old one
    assert len(set(demo.exclude(username='demo-old').values_list('password', flat=True))) == 1
    nadia, tester = User.objects.get(username='demo-nadia'), User.objects.get(pk=tester.pk)
    assert nadia.check_password(PASSWORD) and tester.check_password(PASSWORD) and tester.is_active
    assert (nadia.email, nadia.display_name, nadia.address_form, nadia.preferred_language, nadia.is_staff) == (
        'demo-nadia@demo.law.invalid', 'نادية', 'f', 'ar', False)
    assert (nadia.date_joined, nadia.email_proven_at, nadia.check_consent_at) == (
        MOMENT - timedelta(days=90), MOMENT - timedelta(days=60), MOMENT)
    assert User.objects.get(username='demo-meryem').preferred_language == 'fr'
    assert User.objects.get(username='demo-staff').is_staff
    new, unproven = User.objects.get(username='demo-new'), User.objects.get(username='demo-unproven')
    assert (tester.check_consent_at, new.check_consent_at, unproven.check_consent_at) == (None, None, None)
    assert (new.date_joined, new.email_proven_at) == (MOMENT, MOMENT - timedelta(days=60))
    assert unproven.email_proven_at is None
    assert f'password for every demo account: {PASSWORD}' in out
    assert out.startswith(f'{Contribution.objects.filter(discussion__path__startswith="/talk/").count()} contributions')

    # Every topic has a moderator from its community.
    covered = {p for r in Reviewer.objects.filter(user__in=demo, ended_at=None) for p in r.text_paths}
    assert covered == {p.path for p in places.all_places()}
    assert Reviewer.objects.get(user__username='demo-zineb', ended_at=None).text_paths == [
        '/talk/road', '/talk/health', '/talk/business', '/talk/general']

    # The family topic: article 49's questions, dated over three weeks, the first quoting the article.
    family = Contribution.objects.filter(discussion__path='/talk/family', parent=None)
    asked = family.filter(about=seed.ART_49, kind='question').order_by('created_at')
    assert asked.count() == 14 and family.filter(about=seed.ART_49, kind='post').count() == 5
    # Asked in turn by every third person, a day and a third apart, every third quoting the article's next words.
    names = [p[0] for p in words.PEOPLE] + ['tester']
    assert [(q.author.username, q.quote, q.created_at) for q in asked] == [
        (f'demo-{names[(i * 3 + 1) % len(names)]}', words.ART49_QUOTES[i // 3] if i % 3 == 0 else '',
         MOMENT - timedelta(days=20 - i * 1.3)) for i in range(14)]
    first = asked.first()
    assert (first.title, first.quote, first.created_at, first.author.username) == (
        'خدمت مع راجلي 18 عام، الدار مسجلة باسمو بوحدو.…؟', words.ART49_QUOTES[0], MOMENT - timedelta(days=20),
        'demo-youssef')
    assert first.replies.filter(accepted_at__isnull=False).count() == 1
    def quotes(path):
        return list(Contribution.objects.filter(about=path, parent=None, kind='question').order_by('created_at')
                    .values_list('quote', flat=True))
    cheque = '/ma/dahir/1-59-413/art_480'
    assert quotes(cheque) == [words.SMALL[cheque]['quotes'][0]] + [''] * (len(words.SMALL[cheque]['questions']) - 1)
    assert quotes('/ma/loi/50-25/art_7') == [''] * len(words.SMALL['/ma/loi/50-25/art_7']['questions'])
    rent = Contribution.objects.get(title=seed.HOUSING_POSTS[0][1])
    assert (rent.about, rent.quote, rent.created_at) == ('/ma/loi/67-12/art_34', seed.HOUSING_POSTS[0][4],
                                                         MOMENT - timedelta(days=4))
    held = Contribution.objects.get(title='محامية مزيانة فهاد الملفات')
    assert held.held_reasons == ['phone'] and held.created_at == MOMENT - timedelta(hours=0.4 * 24)
    shared = Contribution.objects.get(body=words.REPORTED_49[0])
    assert sorted(shared.reports.values_list('reporter__username', 'reason')) == [
        ('demo-ayoub', 'abuse'), ('demo-loubna', 'abuse')]
    road = Contribution.objects.get(title=demo_cases.POSTS[0]['title'])
    assert Useful.objects.filter(contribution=road).count() == road.useful_count == 4
    assert road.replies.get(accepted_at__isnull=False).author.username == 'demo-rachid'

    # What the screenshots and the end-to-end script find in each topic, and the votes and marks they show.
    written = (Contribution.objects.filter(author__in=demo).values('discussion__path')
               .annotate(posts=Count('pk', filter=Q(parent=None)), comments=Count('pk', filter=Q(parent__isnull=False))))
    assert {r['discussion__path']: (r['posts'], r['comments']) for r in written} == {
        '/talk/business': (3, 3), '/talk/consumer': (4, 3), '/talk/digital': (3, 1), '/talk/family': (43, 39),
        '/talk/general': (2, 2), '/talk/health': (2, 2), '/talk/housing': (8, 39), '/talk/justice': (7, 3),
        '/talk/land': (3, 2), '/talk/papers': (2, 1), '/talk/road': (4, 6), '/talk/tax': (6, 3), '/talk/work': (5, 2)}
    assert (Useful.objects.count(), Contribution.objects.exclude(accepted_at=None).count()) == (315, 14)
    assert not Contribution.objects.filter(parent__isnull=False, active_at__isnull=False).exists()

    # The states, each printed with its address and its author.
    printed = {line.split()[0]: line.split()[1:] for line in out.splitlines()[1:]}
    assert set(printed) == {'long_thread', *(s[0] for s in demo_cases.STATES)}
    state = {name: Contribution.objects.get(pk=int(where.rsplit('/', 1)[1])) for name, (where, _, by) in printed.items()}
    for name, topic, who, *_ in demo_cases.STATES:
        assert printed[name] == [f'/talk/{topic}/{state[name].pk}', 'by', f'demo-{who}']
    assert state['held_pattern'].held_reasons == ['phone']
    assert (state['held_check'].held_reasons, state['held_check'].held_at) == (['check_respect'],
                                                                             MOMENT - timedelta(hours=3))
    looks = Check.objects.filter(user__username='demo-soukaina').order_by('pk')
    assert [(c.outcome, c.rule, c.model, c.contribution_id) for c in looks] == [
        ('return', 'privacy', 'demo', None), ('return', 'privacy', 'demo', state['returned_sent'].pk)]
    assert Check.objects.get(contribution=state['unavailable']).failure == 'timeout'
    assert state['sent_back'].review_note.startswith('احذف اسم مول المحل')
    assert '0600000003' not in state['redacted'].body and '[حُذف]' in state['redacted'].body
    assert '0600000003' in Revision.objects.get(contribution=state['redacted']).body
    assert state['hidden'].hidden_at == MOMENT and state['hidden'].reports.filter(reason='exposing').count() == 3
    assert list(state['reported'].reports.values_list('reason', 'details')) == [('soliciting', 'كيعرض خدماتو بالثمن')] * 2
    removed = state['removed_with_replies']
    assert (removed.removed_rule, removed.removed_by.username, removed.replies.count()) == ('respect', 'demo-zineb', 2)
    assert Appeal.objects.get(contribution=removed).user.username == 'demo-said'
    assert Ban.objects.filter(user__username='demo-said', until=MOMENT + timedelta(days=7), rule='respect').exists()
    assert state['deleted_with_replies'].deleted_at == MOMENT
    assert state['duplicate'].duplicate_of.title == 'شريت أونلاين وبغيت نرجع السلعة'
    assert state['edited'].body.endswith('le reçu de la caution.') and state['edited'].edited_at == MOMENT
    assert Trust.objects.filter(user__username='demo-meryem', by__username='demo-khadija', ended_at=None).exists()
    thread = state['long_thread']
    assert thread.title == demo_cases.THREAD['title'] and thread.replies.count() == 1 + len(demo_cases.THREAD['replies'])
    assert thread.replies.get(author__username='demo-khalid').removed_rule == 'respect'
    assert thread.replies.get(accepted_at__isnull=False).author.username == 'demo-khadija'

    # The tester's corner: their question answered and marked, a topic followed.
    mine = Contribution.objects.get(author__username='demo-tester', title='واش المكري يقدر يدخل للدار بلا إذن؟')
    assert mine.replies.get(accepted_at__isnull=False).author.username == 'demo-khadija'
    assert Follow.objects.filter(user__username='demo-tester', path='/talk/family').exists()

    # Counted again once everything is dated: a post's last sign of life is its latest published comment's.
    live = Q(replies__held_at=None, replies__removed_at=None, replies__deleted_at=None, replies__hidden_at=None)
    posts = Contribution.objects.filter(discussion__path__startswith='/talk/', parent=None, author__in=demo) \
        .annotate(last=Max('replies__created_at', filter=live))
    assert posts.filter(last__isnull=False).count() > 40
    assert all(p.active_at == max(p.created_at, p.last or p.created_at) for p in posts)
    room = Discussion.objects.get(path='/talk/family')
    published = Contribution.objects.filter(discussion=room, held_at=None, hidden_at=None, removed_at=None,
                                            deleted_at=None)
    assert room.count == published.count() and room.count > 30
