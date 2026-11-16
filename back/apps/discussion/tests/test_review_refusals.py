"""What the desk refuses and the acts' edges: an act with nothing to act on, what is not there, spans that cannot be
read, a repeat that is no repeat, a pause or an appeal out of place; and what an act leaves when something else
still keeps a post from readers (a hold, a deletion under a report)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.discussion.models import (APPEAL_MAX, NOTE_MAX, Action, Appeal, Ban, Contribution, Discussion, Notice, Report,
                                    Reviewer, Revision, Trust)
from apps.discussion.services import points, review
from apps.discussion.services.review.acts import KEPT
from apps.discussion.tests.conftest import PATH, make_user, signed_in
from apps.media.models import Picture, State

pytestmark = pytest.mark.django_db


def act(api, user, pk, **data):
    return signed_in(api, user).post(f'/api/discussion/review/contributions/{pk}/', data, format='json')


def errors(r):
    return r.status_code, [(e['field'], e['code']) for e in r.json()['errors']]


@pytest.fixture
def place():
    return Discussion.objects.create(path=PATH, text_path=PATH)


@pytest.fixture
def moderator(staff):
    user = make_user('rev')
    review.appoint(staff, user, [PATH])
    return user


def post(place, author, kind='post', **fields) -> Contribution:
    return Contribution.objects.create(discussion=place, author=author, kind=kind, title='منشور', body='كلام عادي',
                                       **fields)


def test_an_act_with_nothing_to_act_on_is_refused(api, place, moderator):
    author = make_user('salma')
    shown = post(place, author)
    for verb in ('approve', 'keep', 'restore'):
        assert errors(act(api, moderator, shown.pk, act=verb)) == (409, [('review', 'nothing_waiting')]), verb
    for note in ({}, {'note': '   '}):
        assert errors(act(api, moderator, shown.pk, act='send_back', **note)) == (400, [('note', 'required')])
    assert act(api, moderator, shown.pk, act='remove', rule='respect').status_code == 200
    assert errors(act(api, moderator, shown.pk, act='remove', rule='privacy')) == (409, [('review', 'nothing_waiting')])
    assert errors(act(api, moderator, shown.pk, act='send_back', note='عدل')) == (409, [('review', 'nothing_waiting')])
    # Held, but removed or deleted: nothing to publish.
    now = timezone.now()
    for gone in ({'removed_at': now}, {'deleted_at': now}):
        held = post(place, author, held_at=now, held_reasons=['phone'], **gone)
        assert errors(act(api, moderator, held.pk, act='approve')) == (409, [('review', 'nothing_waiting')])
    deleted = post(place, author, deleted_at=now)
    assert errors(act(api, moderator, deleted.pk, act='send_back', note='عدل')) == (409, [('review', 'nothing_waiting')])
    # Removed more than 90 days ago: too late to restore.
    Contribution.objects.filter(pk=shown.pk).update(removed_at=now - timedelta(days=91))
    assert errors(act(api, moderator, shown.pk, act='restore')) == (409, [('review', 'nothing_waiting')])
    assert list(Action.objects.exclude(verb='appoint').values_list('verb', flat=True)) == ['remove']
    assert Contribution.objects.get(pk=shown.pk).removed_rule == 'respect'


def test_what_is_not_there_answers_404(api, place, moderator, staff):
    named = post(place, make_user('salma'))
    assert errors(act(api, staff, named.pk, act='reveal', note='تهديد')) == (404, [('contribution', 'not_found')])
    hidden_name = post(place, make_user('ali'), anonymous=True)
    assert errors(act(api, staff, hidden_name.pk, act='reveal', note='   ')) == (400, [('note', 'required')])
    erased = post(place, make_user('omar'), erased_at=timezone.now())
    for pk in (erased.pk, erased.pk + 100):
        assert errors(act(api, moderator, pk, act='approve')) == (404, [('contribution', 'not_found')])
    r = signed_in(api, moderator).post('/api/discussion/review/lock/', {'path': '/talk/family', 'locked': True},
                                       format='json')
    assert errors(r) == (404, [('path', 'not_found')])
    ended = Ban.objects.create(user=named.author, rule='respect', via=named, until=timezone.now() + timedelta(days=3),
                               ended_at=timezone.now())
    for pk in (999, ended.pk):
        r = signed_in(api, staff).post(f'/api/discussion/review/pauses/{pk}/', {'act': 'lift'}, format='json')
        assert errors(r) == (404, [('pause', 'not_found')])
    assert not Action.objects.filter(verb__in=['reveal', 'lock', 'unban']).exists()


@pytest.mark.parametrize('spans', [[['a', 3]], [[0, 10]], [[4, 2]], [[3, 3]], [[0, 4], [3, 5]], []])
def test_spans_the_desk_cannot_read_are_refused(api, place, moderator, spans):
    held = post(place, make_user('salma'), held_at=timezone.now(), held_reasons=['phone'])
    assert errors(act(api, moderator, held.pk, act='redact', spans=spans)) == (400, [('spans', 'invalid')])
    assert Contribution.objects.get(pk=held.pk).body == 'كلام عادي' and not Revision.objects.exists()


@pytest.mark.parametrize('spans, body', [
    ([[5, 9]], 'كلام [حُذف]'),                      # up to the words' last character
    ([[0, 4], [4, 5]], '[حُذف][حُذف]عادي'),         # touching: one ends where the next begins
])
def test_spans_up_to_the_end_or_touching_are_redacted(api, place, moderator, spans, body):
    held = post(place, make_user('salma'), held_at=timezone.now(), held_reasons=['phone'],
                held_spans=[[0, 4, 'phone']], links=[{'start': 0, 'end': 4, 'path': '/ma/loi/2013/67-12/art_32'}])
    assert act(api, moderator, held.pk, act='redact', spans=spans, publish=False).status_code == 200
    held.refresh_from_db()
    assert (held.body, held.held_reasons, held.held_spans, held.links) == (body, [], [], [])


def test_redacting_without_publishing_leaves_the_post_waiting(api, place, moderator):
    held = post(place, make_user('salma'), held_at=timezone.now(), held_reasons=['phone', 'pictures'])
    assert act(api, moderator, held.pk, act='redact', spans=[[0, 4]], publish=False).status_code == 200
    held.refresh_from_db()
    assert (held.body, held.held_reasons) == ('[حُذف] عادي', ['pictures']) and held.held_at is not None
    assert Revision.objects.get(contribution=held).body == 'كلام عادي'
    assert list(Action.objects.exclude(verb='appoint').values_list('verb', flat=True)) == ['redact']


def test_keeping_a_hidden_post_brings_its_pictures_back_unless_a_hold_keeps_it(api, place, moderator):
    now = timezone.now()
    pictures = {}
    # Hidden with no report left open; hidden, held and reported.
    for name, held in (('shown', None), ('held', now)):
        c = post(place, make_user(name), hidden_at=now, held_at=held, held_reasons=['phone'] if held else [])
        c.pictures.add(Picture.objects.create(owner=c.author, state=State.EVIDENCE, width=10, height=10))
        if held:
            Report.objects.create(contribution=c, reporter=make_user(f'{name}-reporter'), reason='exposing')
        assert act(api, moderator, c.pk, act='keep').status_code == 200
        c.refresh_from_db()
        pictures[name] = (c.hidden_at, c.held_at is not None, c.pictures.get().state)
    assert pictures == {'shown': (None, False, State.LIVE), 'held': (None, True, State.EVIDENCE)}
    # Reported, never hidden.
    reported = post(place, make_user('third'))
    Report.objects.create(contribution=reported, reporter=make_user('third-reporter'), reason='abuse')
    assert act(api, moderator, reported.pk, act='keep').status_code == 200
    assert list(Report.objects.values_list('status', 'decided_by')) == [('reviewed', moderator.pk)] * 2
    assert not Report.objects.filter(decided_at=None).exists()
    assert list(Action.objects.filter(verb='keep').values_list('contribution', flat=True).order_by('pk')) == [
        Contribution.objects.get(title='منشور', author__username='shown').pk,
        Contribution.objects.get(author__username='held').pk, reported.pk]


def test_a_post_deleted_under_a_report_is_removed_without_telling_its_author_and_restored_without_its_points(
        api, place, moderator):
    author, reader = make_user('salma'), make_user('hamid')
    c = post(place, author)
    signed_in(api, make_user('voter')).post(f'/api/discussion/contributions/{c.pk}/useful/')
    signed_in(api, reader).post(f'/api/discussion/contributions/{c.pk}/report/', {'reason': 'abuse'}, format='json')
    assert points.total(author) == 1
    assert signed_in(api, author).delete(f'/api/discussion/contributions/{c.pk}/').status_code == 204
    assert act(api, moderator, c.pk, act='remove', rule='respect').status_code == 200
    assert not Notice.objects.filter(user=author, kind='removed').exists()
    assert Notice.objects.filter(user=reader, kind='report', detail='acted').exists()
    assert act(api, moderator, c.pk, act='restore').status_code == 200
    c.refresh_from_db()
    assert c.removed_at is None and c.deleted_at is not None and not c.published
    assert points.total(author) == 0 and Notice.objects.filter(user=author, kind='restored').exists()


def test_untrusting_ends_the_trust_once(api, place, moderator):
    author = make_user('salma')
    c = post(place, author)
    for verb in ('trust', 'trust', 'untrust', 'untrust'):
        assert act(api, moderator, c.pk, act=verb).status_code == 200
    trust = Trust.objects.get(user=author)
    assert trust.ended_at is not None and trust.by == moderator
    assert list(Action.objects.exclude(verb='appoint').values_list('verb', flat=True).order_by('pk')) == [
        'trust', 'untrust']


def test_a_repeat_is_a_question_marked_after_a_published_question_of_its_place(api, place, moderator):
    asker = make_user('salma')
    first = post(place, make_user('omar'), kind='question')
    asked = post(place, asker, kind='question')
    comment = Contribution.objects.create(discussion=place, author=asker, parent=first, kind='comment', body='نفس')
    told = post(place, asker)
    waiting = post(place, make_user('karim'), kind='question', held_at=timezone.now(), held_reasons=['phone'])
    elsewhere = post(Discussion.objects.create(path='/talk/work', text_path='/talk/work'), asker, kind='question')
    for pk, of in ((comment.pk, first.pk), (told.pk, first.pk), (asked.pk, asked.pk), (asked.pk, waiting.pk),
                   (asked.pk, told.pk), (asked.pk, elsewhere.pk), (asked.pk, None)):
        assert errors(act(api, moderator, pk, act='duplicate', of=of)) == (400, [('duplicate', 'invalid')]), (pk, of)
    assert Contribution.objects.filter(duplicate_of__isnull=False).count() == 0
    assert act(api, moderator, asked.pk, act='duplicate', of=first.pk).status_code == 200
    assert Contribution.objects.get(pk=asked.pk).duplicate_of == first
    assert Action.objects.get(verb='duplicate').rule == 'on_topic'
    assert Notice.objects.get(user=asker, kind='duplicate').contribution == first


def test_a_pause_names_its_rule_and_is_decided_where_it_was_made(api, place, moderator, staff):
    author = make_user('salma')
    c = post(place, author)
    assert errors(act(api, moderator, c.pk, act='pause', days=3)) == (400, [('rule', 'required')])
    assert act(api, moderator, c.pk, act='pause', days=3, rule='respect').status_code == 200
    ban = Ban.objects.get(user=author)
    elsewhere = make_user('elsewhere')
    review.appoint(staff, elsewhere, ['/talk/work'])
    r = signed_in(api, elsewhere).post(f'/api/discussion/review/pauses/{ban.pk}/', {'act': 'lift'}, format='json')
    assert errors(r) == (403, [('review', 'not_reviewer')])
    r = signed_in(api, staff).post(f'/api/discussion/review/pauses/{ban.pk}/', {'act': 'confirm'}, format='json')
    assert errors(r) == (409, [('review', 'nothing_waiting')])
    ban.refresh_from_db()
    assert ban.ended_at is None and ban.until is not None and ban.rule == 'respect'
    # Made through no post, only staff see it; one whose maker's account is gone, a moderator lifts.
    loose = Ban.objects.create(user=make_user('omar'), rule='respect', until=timezone.now() + timedelta(days=3))
    r = signed_in(api, moderator).post(f'/api/discussion/review/pauses/{loose.pk}/', {'act': 'lift'}, format='json')
    assert errors(r) == (403, [('review', 'not_reviewer')])
    Ban.objects.filter(pk=ban.pk).update(by=None)
    r = signed_in(api, moderator).post(f'/api/discussion/review/pauses/{ban.pk}/', {'act': 'lift'}, format='json')
    assert r.status_code == 200 and Ban.objects.get(pk=ban.pk).ended_at is not None
    assert Ban.objects.get(pk=loose.pk).ended_at is None
    # A pause asked for good, confirmed by a second eye: for good, and asked by nobody any more.
    other = post(place, make_user('karim'))
    act(api, moderator, other.pk, act='pause', days='permanent', rule='respect')
    asked = Ban.objects.get(user=other.author)
    signed_in(api, staff).post(f'/api/discussion/review/pauses/{asked.pk}/', {'act': 'confirm'}, format='json')
    asked.refresh_from_db()
    assert (asked.until, asked.permanent_asked_by, asked.ended_at) == (None, None, None)


def test_an_appeal_is_on_ones_own_removal_or_pause_and_says_what_came_of_it(api, place, moderator, staff):
    author = make_user('salma')
    mine, theirs = post(place, author), post(place, make_user('omar'))
    act(api, moderator, mine.pk, act='pause', days=7, rule='respect')
    ban = Ban.objects.get(user=author)
    other_ban = Ban.objects.create(user=make_user('karim'), until=timezone.now() + timedelta(days=3), rule='respect')

    def appeal(**data):
        return signed_in(api, author).post('/api/discussion/appeals/', data, format='json')

    assert errors(appeal(pause=ban.pk, text='x' * (APPEAL_MAX + 1))) == (400, [('text', 'too_long')])
    assert errors(appeal(pause=ban.pk, text='   ')) == (400, [('text', 'required')])
    gone = post(place, author, removed_at=timezone.now(), removed_rule='respect', erased_at=timezone.now())
    for pk in (mine.pk, theirs.pk, gone.pk):           # not removed; someone else's; erased since
        assert errors(appeal(contribution=pk, text='ظلم')) == (404, [('contribution', 'not_found')])
    assert errors(appeal(pause=other_ban.pk, text='ظلم')) == (404, [('pause', 'not_found')])
    assert not Appeal.objects.exists()
    words = 'ظ' * APPEAL_MAX
    assert appeal(pause=ban.pk, text=f'  {words} ').status_code == 201
    a = Appeal.objects.get()
    assert (a.user, a.ban, a.contribution, a.text) == (author, ban, None, words)
    assert signed_in(api, author).get('/api/discussion/me/').json()['pause']['appeal'] == {
        'created_at': a.created_at.isoformat().replace('+00:00', 'Z'), 'decided': False, 'outcome': None}

    def decide(user, outcome):
        return signed_in(api, user).post(f'/api/discussion/review/appeals/{a.pk}/', {'outcome': outcome},
                                         format='json')

    assert errors(decide(moderator, 'lifted')) == (403, [('review', 'second_eye')])     # who paused
    assert errors(decide(staff, 'maybe')) == (400, [('outcome', 'invalid')])
    before = timezone.now()
    assert decide(staff, 'lifted').status_code == 200
    a = Appeal.objects.get(pk=a.pk)
    assert (a.outcome, a.decided_by) == ('lifted', staff) and before <= a.decided_at <= timezone.now()
    assert errors(decide(staff, 'kept')) == (404, [('appeal', 'not_found')])
    ban.refresh_from_db()
    assert ban.ended_at is not None
    assert errors(appeal(pause=ban.pk, text='مرة أخرى')) == (404, [('pause', 'not_found')])     # it no longer runs
    assert list(Action.objects.filter(target=author).values_list('verb', 'actor').order_by('pk')) == [
        ('ban', moderator.pk), ('unban', staff.pk), ('appeal_lift', staff.pk)]
    assert Notice.objects.filter(user=author, kind='appeal', detail='lifted').exists()
    assert signed_in(api, author).get('/api/discussion/me/').json()['pause'] is None


def test_an_appeal_against_a_pause_already_lifted_is_decided_without_lifting_again(api, place, moderator, staff):
    author = make_user('salma')
    act(api, moderator, post(place, author).pk, act='pause', days=7, rule='respect')
    ban = Ban.objects.get(user=author)
    a = Appeal.objects.create(user=author, ban=ban, text='ظلم')
    signed_in(api, staff).post(f'/api/discussion/review/pauses/{ban.pk}/', {'act': 'lift'}, format='json')
    ended = Ban.objects.get(pk=ban.pk).ended_at
    assert signed_in(api, staff).post(f'/api/discussion/review/appeals/{a.pk}/', {'outcome': 'lifted'},
                                      format='json').status_code == 200
    assert Ban.objects.get(pk=ban.pk).ended_at == ended
    assert list(Action.objects.filter(target=author).values_list('verb', flat=True).order_by('pk')) == [
        'ban', 'unban', 'appeal_lift']


def test_a_moderator_of_everything_decides_appeals_and_reads_the_ledger_of_every_place(api, staff):
    everywhere, nobody = make_user('rev'), make_user('nobody')
    review.appoint(staff, everywhere, everywhere=True)
    work = Discussion.objects.create(path='/talk/work', text_path='/talk/work')
    removed = post(work, make_user('salma'), removed_at=timezone.now(), removed_by=staff, removed_rule='respect')
    Appeal.objects.create(user=removed.author, contribution=removed, text='ظلم')
    Action.objects.create(actor=staff, verb='remove', contribution=removed, path='/talk/work')
    queue = signed_in(api, everywhere).get('/api/discussion/review/', {'tab': 'appeals'}).json()
    assert [i['contribution']['id'] for i in queue['items']] == [removed.pk] and queue['counts']['appeals'] == 1
    ledger = signed_in(api, everywhere).get('/api/discussion/review/ledger/').json()['actions']
    assert [(a['verb'], a['path']) for a in ledger] == [('remove', '/talk/work'), ('appoint', None)]
    assert errors(signed_in(api, nobody).get('/api/discussion/review/ledger/')) == (403, [('review', 'not_reviewer')])


def test_only_staff_appoint_and_end_moderators(api, moderator, staff):
    target = make_user('salma')
    r = signed_in(api, moderator).post('/api/discussion/review/reviewers/', {'username': 'salma', 'places': ['work']},
                                       format='json')
    assert errors(r) == (403, [('review', 'staff_only')])
    assert errors(signed_in(api, moderator).delete(f'/api/discussion/review/reviewers/{moderator.pk}/')) == (
        403, [('review', 'staff_only')])
    assert Reviewer.objects.get(user=moderator).ended_at is None and not Reviewer.objects.filter(user=target).exists()
    # Places may come as one comma-separated line of addresses.
    r = signed_in(api, staff).post('/api/discussion/review/reviewers/',
                                   {'username': 'SALMA', 'text_paths': '/talk/work, /talk/family,'}, format='json')
    assert r.status_code == 201
    assert Reviewer.objects.get(user=target).text_paths == ['/talk/work', '/talk/family']


def test_nobody_decides_about_their_own_words_nor_where_they_do_not_moderate(api, place, moderator, staff):
    mine = post(place, moderator, held_at=timezone.now(), held_reasons=['phone'])
    for data in ({'act': 'approve'}, {'act': 'remove', 'rule': 'respect'}, {'act': 'trust'}):
        assert errors(act(api, moderator, mine.pk, **data)) == (403, [('review', 'own')])
    Discussion.objects.create(path='/talk/work', text_path='/talk/work')
    r = signed_in(api, moderator).post('/api/discussion/review/lock/', {'path': '/talk/work', 'locked': True},
                                       format='json')
    assert errors(r) == (403, [('review', 'not_reviewer')])
    assert Discussion.objects.get(path='/talk/work').locked_at is None
    assert Contribution.objects.get(pk=mine.pk).held_at is not None and not Trust.objects.exists()
    assert act(api, staff, mine.pk, act='approve').status_code == 200


def test_one_who_follows_a_held_post_and_its_topic_hears_once_when_it_is_published(api, place, moderator, staff):
    held = post(place, make_user('salma'), held_at=timezone.now(), held_reasons=['phone'])
    reader = make_user('hamid')
    for user, paths in ((moderator, (PATH, f'{PATH}/{held.pk}')), (reader, (PATH,))):
        for path in paths:
            r = signed_in(api, user).post('/api/discussion/follow/', {'path': path}, format='json')
            assert r.json() == {'following': True}
    assert act(api, staff, held.pk, act='approve').status_code == 200
    heard = Notice.objects.filter(kind='new').order_by('user_id')
    assert list(heard.values_list('user__username', 'path')) == [('rev', f'{PATH}/{held.pk}'), ('hamid', PATH)]


def test_a_removal_is_written_whole_and_a_restore_takes_it_back_whole(api, place, moderator):
    now = timezone.now()
    c = post(place, make_user('salma'), hidden_at=now, post_review_at=now)
    reporter = make_user('hamid')
    Report.objects.create(contribution=c, reporter=reporter, reason='exposing')
    assert act(api, moderator, c.pk, act='remove', rule='privacy', note='اسم كامل').status_code == 200
    c.refresh_from_db()
    assert (c.removed_by, c.removed_rule, c.hidden_at, c.post_review_at) == (moderator, 'privacy', None, None)
    assert c.removed_at is not None
    report = Report.objects.get()
    assert (report.status, report.decided_by) == ('acted', moderator) and report.decided_at is not None
    assert Action.objects.get(verb='remove').note == 'اسم كامل'
    assert act(api, moderator, c.pk, act='restore').status_code == 200
    c.refresh_from_db()
    assert (c.removed_at, c.removed_by, c.removed_rule) == (None, None, '') and c.published


def test_a_removal_is_restored_up_to_its_ninetieth_day_and_never_once_erased(api, place, moderator, staff,
                                                                             monkeypatch):
    moment = timezone.now()
    monkeypatch.setattr(timezone, 'now', lambda: moment)        # the clock held still
    on, past = (post(place, make_user(name), removed_at=moment - KEPT - late, removed_by=staff, removed_rule='respect')
                for name, late in (('salma', timedelta(0)), ('omar', timedelta(seconds=1))))
    assert act(api, moderator, on.pk, act='restore').status_code == 200
    assert errors(act(api, moderator, past.pk, act='restore')) == (409, [('review', 'nothing_waiting')])
    assert Contribution.objects.get(pk=on.pk).removed_at is None
    assert Contribution.objects.get(pk=past.pk).removed_at == moment - KEPT - timedelta(seconds=1)
    # Appealed, then erased before the appeal was decided: nothing left to restore, and the appeal stays open.
    erased = post(place, make_user('karim'), removed_at=moment, removed_by=moderator, removed_rule='respect')
    a = Appeal.objects.create(user=erased.author, contribution=erased, text='ظلم')
    Contribution.objects.filter(pk=erased.pk).update(erased_at=moment)
    r = signed_in(api, staff).post(f'/api/discussion/review/appeals/{a.pk}/', {'outcome': 'lifted'}, format='json')
    assert errors(r) == (409, [('review', 'nothing_waiting')])
    a.refresh_from_db()
    assert (a.decided_at, a.outcome, a.decided_by) == (None, '', None)


def test_an_appeal_is_decided_by_neither_its_writer_nor_a_moderator_of_elsewhere(api, place, moderator, staff):
    writer = make_user('boss', staff=True)
    c = post(place, writer, removed_at=timezone.now(), removed_by=moderator, removed_rule='respect')
    a = Appeal.objects.create(user=writer, contribution=c, text='ظلم')
    elsewhere = make_user('elsewhere')
    review.appoint(staff, elsewhere, ['/talk/work'])

    def decide(user, outcome='kept'):
        return signed_in(api, user).post(f'/api/discussion/review/appeals/{a.pk}/', {'outcome': outcome},
                                         format='json')

    for user in (writer, elsewhere):
        assert errors(decide(user)) == (403, [('review', 'second_eye')])
    assert decide(staff).status_code == 200
    a.refresh_from_db()
    assert (a.outcome, a.decided_by) == ('kept', staff)
    assert Contribution.objects.get(pk=c.pk).removed_rule == 'respect'
    assert Action.objects.get(verb='appeal_keep').target == writer
    assert Notice.objects.get(user=writer, kind='appeal').detail == 'kept'


def test_sending_back_keeps_a_note_as_long_as_its_column(api, place, moderator):
    c = post(place, make_user('salma'), post_review_at=timezone.now(), held_reasons=['returned'])
    note = 'ن' * (NOTE_MAX + 5)
    assert act(api, moderator, c.pk, act='send_back', note=f'  {note}  ').status_code == 200
    c.refresh_from_db()
    assert (c.review_note, c.held_reasons, c.post_review_at) == ('ن' * NOTE_MAX, ['sent_back'], None)
    assert c.held_at is not None
    assert Action.objects.get(verb='send_back').note == 'ن' * NOTE_MAX
    assert Notice.objects.get(user=c.author, kind='sent_back').detail == 'ن' * 40


def test_a_lock_names_who_locked_and_an_unlock_clears_it(api, place, moderator):
    def lock(locked):
        return signed_in(api, moderator).post('/api/discussion/review/lock/', {'path': PATH, 'locked': locked,
                                                                               'note': 'نقاش حاد'}, format='json')

    assert lock(True).json() == {'locked': True}
    place.refresh_from_db()
    assert place.locked_by == moderator and place.locked_at is not None
    assert lock(False).json() == {'locked': False}
    place.refresh_from_db()
    assert (place.locked_at, place.locked_by) == (None, None)
    assert list(Action.objects.filter(path=PATH).values_list('verb', 'note').order_by('pk')) == [
        ('lock', 'نقاش حاد'), ('unlock', 'نقاش حاد')]
