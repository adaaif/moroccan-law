"""A writer's edges: where a comment may hang, words past their length, what an edit refuses or leaves alone, a bare
«المادة 32» read in the text the post started from, «مفيد» and «أفادني» tapped twice or taken back, a voice's link
and a draft thrown away, a report's moment in a voice, and the check when the model's answer cannot be read."""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.tests import claude
from apps.discussion.models import (BODY_MAX, NOTE_MAX, QUOTE_MAX, TITLE_MAX, Check, Contribution, Discussion, Notice,
                                    Report, Revision, Useful)
from apps.discussion.services import points, review
from apps.discussion.tests.conftest import ARTICLE, PATH, TITLE, make_user, settle, signed_in
from apps.media.models import Clip, Picture, State
from apps.media.services import store
from apps.sources.models import Issue

pytestmark = pytest.mark.django_db


def write(api, user, **data):
    sent = {'path': PATH, 'kind': 'question', **({} if data.get('parent') else {'title': TITLE}), 'body': 'سؤال', **data}
    return signed_in(api, user).post('/api/discussion/contributions/', sent, format='json')


def errors(r):
    return r.status_code, [(e['field'], e['code']) for e in r.json()['errors']]


def edit(api, user, pk, **data):
    return signed_in(api, user).patch(f'/api/discussion/contributions/{pk}/', data, format='json')


@pytest.fixture
def other():
    return settle(make_user('amine'), None)


def test_a_comment_hangs_under_a_published_post_and_a_published_answer(api, writer, other):
    q = write(api, writer).json()
    held = write(api, writer, body='اتصلوا بي 0600000000').json()
    for parent in (q['id'] + 1000, held['id']):
        assert errors(write(api, other, parent=parent, body='جواب')) == (404, [('parent', 'not_found')])
    answer = write(api, other, parent=q['id'], body='جواب').json()
    waiting = write(api, other, parent=q['id'], body='رقمي 0600000001').json()
    assert waiting['held'] is True
    assert errors(write(api, writer, parent=waiting['id'], body='شكرا')) == (404, [('parent', 'not_found')])
    assert errors(write(api, writer, parent=answer['id'], body='   ')) == (400, [('body', 'required')])
    thanks = Contribution.objects.get(pk=write(api, writer, parent=answer['id'], body='شكرا').json()['id'])
    assert (thanks.parent_id, thanks.reply_to_id, thanks.kind, thanks.title) == (q['id'], answer['id'], 'comment', '')


def test_words_past_their_length_are_refused(api, writer):
    assert errors(write(api, writer, body='ك' * (BODY_MAX + 1))) == (400, [('body', 'too_long')])
    assert errors(write(api, writer, quote='ق' * (QUOTE_MAX + 1))) == (400, [('quote', 'too_long')])
    # As long as it may be, a quote is then read against the article: with none, it is in none.
    assert errors(write(api, writer, quote='ق' * QUOTE_MAX)) == (400, [('quote', 'not_in_article')])
    assert write(api, writer, body='ك' * BODY_MAX).status_code == 201
    assert Contribution.objects.filter(discussion__path=PATH).count() == 1


@pytest.mark.parametrize('title, stored', [
    ('كر', None), (' ك \t ر ', 'ك ر'), ('ع' * TITLE_MAX, 'ع' * TITLE_MAX), ('ع' * (TITLE_MAX + 1), None)])
def test_a_posts_title_is_three_to_140_characters_once_its_spaces_are_one(api, writer, title, stored):
    r = write(api, writer, title=title)
    if stored is None:
        assert errors(r) == (400, [('title', 'required' if len(title) < 3 else 'too_long')])
        assert not Contribution.objects.filter(discussion__path=PATH).exists()
    else:
        assert r.status_code == 201 and Contribution.objects.get(pk=r.json()['id']).title == stored


def test_an_edit_holds_the_words_to_the_bounds_of_a_new_post_and_keeps_what_they_were(api, writer, other, lease):
    q = write(api, writer).json()

    def stored(pk=q['id']):
        return Contribution.objects.get(pk=pk)

    assert edit(api, writer, q['id'], body='ك' * BODY_MAX).status_code == 200 and stored().body == 'ك' * BODY_MAX
    assert errors(edit(api, writer, q['id'], body='ك' * (BODY_MAX + 1))) == (400, [('body', 'too_long')])
    for title in ('كرا', 'ع' * TITLE_MAX):
        assert edit(api, writer, q['id'], body='سؤال', title=title).status_code == 200 and stored().title == title
    edit(api, writer, q['id'], body='سؤال', title='زيادة\t  في\nالكراء ')
    assert stored().title == 'زيادة في الكراء' and stored().edited_at is not None
    assert list(Revision.objects.filter(contribution_id=q['id']).values_list('body', flat=True).order_by('pk'))[:2] == [
        f'{TITLE}\n\nسؤال', f'{TITLE}\n\n' + 'ك' * BODY_MAX]
    # A comment has no title, whatever the edit sends; its earlier words are kept without one.
    answer = write(api, other, parent=q['id'], body='جواب').json()
    assert edit(api, other, answer['id'], body='جواب معدل', title='عنوان').status_code == 200
    assert (stored(answer['id']).title, stored(answer['id']).body) == ('', 'جواب معدل')
    assert Revision.objects.get(contribution_id=answer['id']).body == 'جواب'
    # An article thread of before needs no title.
    old = Discussion.objects.create(path=ARTICLE, text_path='/ma/loi/2013/67-12')
    then = Contribution.objects.create(discussion=old, author=writer, kind='question', body='سؤال قديم')
    assert edit(api, writer, then.pk, body='سؤال قديم معدل').status_code == 200
    assert (stored(then.pk).title, stored(then.pk).body) == ('', 'سؤال قديم معدل')


def test_an_edit_is_refused_where_the_words_could_not_stand_and_does_nothing_when_nothing_changed(api, writer, other):
    q = write(api, writer).json()
    assert errors(edit(api, writer, q['id'], body='ك' * (BODY_MAX + 1))) == (400, [('body', 'too_long')])
    assert errors(edit(api, writer, q['id'], body='سؤال', title='كر')) == (400, [('title', 'required')])
    assert errors(edit(api, writer, q['id'], body='سؤال', title='ع' * 141)) == (400, [('title', 'too_long')])
    same = edit(api, writer, q['id'], body=' سؤال ', title=f' {TITLE} ')
    assert same.status_code == 200 and same.json()['edited_at'] is None
    assert not Revision.objects.exists() and Contribution.objects.get(pk=q['id']).edited_at is None
    answer = write(api, other, parent=q['id'], body='جواب').json()
    assert errors(edit(api, other, answer['id'], body='')) == (400, [('body', 'required')])
    Contribution.objects.filter(pk=answer['id']).update(removed_at=timezone.now(), removed_rule='respect')
    assert errors(edit(api, other, answer['id'], body='جواب آخر')) == (409, [('contribution', 'removed')])
    assert Contribution.objects.get(pk=answer['id']).body == 'جواب'


def test_a_bare_article_in_an_edit_is_the_one_of_the_text_the_post_started_from_while_it_stands(api, writer):
    q = write(api, writer, about=ARTICLE, body='سؤال على المادة').json()
    edit(api, writer, q['id'], body='كما تقول المادة 32')
    assert Contribution.objects.get(pk=q['id']).links == [{'start': 9, 'end': 18, 'path': '/ma/loi/2013/67-12/art_32'}]
    Article.objects.filter(eid='art_34').delete()           # the article it started from, gone from the corpus
    edit(api, writer, q['id'], body='كما تقول المادة 33')
    row = Contribution.objects.get(pk=q['id'])
    assert (row.body, row.links, row.about) == ('كما تقول المادة 33', [], ARTICLE)


def test_pictures_may_come_as_one_line_of_ids(api, writer):
    ids = [str(Picture.objects.create(owner=writer, width=1, height=1).pk) for _ in range(2)]
    r = write(api, writer, kind='post', body='صور', pictures=','.join(ids))
    assert r.status_code == 201
    assert sorted(str(pk) for pk in Contribution.objects.get(pk=r.json()['id']).pictures.values_list('pk', flat=True)) \
        == sorted(ids)


def test_only_the_asker_marks_an_answer_to_their_question_and_a_new_mark_moves_it(api, writer, other):
    q = write(api, writer).json()
    own = write(api, writer, parent=q['id'], body='زيادة من عندي').json()
    first = write(api, other, parent=q['id'], body='جواب').json()
    told = write(api, writer, kind='post', title='منشور', body='.').json()
    under_post = write(api, other, parent=told['id'], body='تعليق').json()

    def accept(pk, method='post'):
        return getattr(signed_in(api, writer), method)(f'/api/discussion/contributions/{pk}/accept/')

    for pk in (own['id'], under_post['id'], q['id']):          # one's own; under a post; a post itself
        assert errors(accept(pk)) == (403, [('accept', 'not_asker')])
    assert errors(accept(q['id'], 'delete')) == (403, [('accept', 'not_asker')])
    karim = settle(make_user('karim'), None)
    second = write(api, karim, parent=q['id'], body='جواب آخر').json()
    accept(first['id'])
    accept(second['id'])
    marked = dict(Contribution.objects.filter(parent_id=q['id']).values_list('pk', 'accepted_at'))
    assert marked[first['id']] is None and marked[second['id']] is not None and marked[own['id']] is None
    assert (points.total(other), points.total(karim)) == (0, 5)
    assert Contribution.objects.get(pk=q['id']).answer_id == second['id']


def test_a_double_tap_counts_once_and_a_mark_taken_back_takes_its_points(api, writer, other, staff):
    q = write(api, writer).json()
    a = write(api, other, parent=q['id'], body='جواب').json()
    voter = make_user('voter')
    for _ in range(2):
        r = signed_in(api, voter).post(f'/api/discussion/contributions/{a["id"]}/useful/')
        assert r.json() == {'useful': 1, 'voted': True}
    assert Useful.objects.filter(contribution_id=a['id']).count() == 1 and points.total(other) == 1
    accept = f'/api/discussion/contributions/{a["id"]}/accept/'
    for _ in range(2):
        assert signed_in(api, writer).post(accept).json() == {'accepted': True}
    assert Notice.objects.filter(user=other, kind='accepted').count() == 1 and points.total(other) == 1 + 5
    assert errors(signed_in(api, voter).delete(accept)) == (403, [('accept', 'not_asker')])
    assert signed_in(api, writer).delete(accept).json() == {'accepted': False}
    assert Contribution.objects.get(pk=a['id']).accepted_at is None and points.total(other) == 1
    assert Contribution.objects.get(pk=q['id']).answer_id == a['id']      # still its answer, unmarked
    # Marked again, removed, restored: the mark's points come back with the vote's.
    signed_in(api, writer).post(accept)
    act = f'/api/discussion/review/contributions/{a["id"]}/'
    signed_in(api, staff).post(act, {'act': 'remove', 'rule': 'on_topic'}, format='json')
    assert points.total(other) == 0
    signed_in(api, staff).post(act, {'act': 'restore'}, format='json')
    assert points.total(other) == 1 + 5


def test_a_voices_link_is_given_to_whoever_may_hear_it_and_a_draft_is_thrown_away_by_its_owner(
        api, writer, reader, django_capture_on_commit_callbacks):
    live = Clip.objects.create(owner=writer, state=State.LIVE, duration_ms=2000, size=4)
    name = store.write('voices', b'take', 'm4a')
    draft = Clip.objects.create(owner=writer, duration_ms=2000, size=4, file_name=name)
    link = api.get(f'/api/discussion/voices/{live.pk}/').json()
    assert link['src'].startswith(f'/api/media/clips/{live.pk}/audio/?t=') and link['expires_at']
    assert errors(api.get(f'/api/discussion/voices/{draft.pk}/')) == (404, [('voice', 'not_found')])
    assert signed_in(api, writer).get(f'/api/discussion/voices/{draft.pk}/').status_code == 200
    api.force_authenticate(None)
    assert errors(api.delete(f'/api/discussion/voices/{draft.pk}/')) == (401, [('account', 'sign_in')])
    assert errors(signed_in(api, reader).delete(f'/api/discussion/voices/{draft.pk}/')) == (404, [('voice', 'not_found')])
    with django_capture_on_commit_callbacks(execute=True):
        assert signed_in(api, writer).delete(f'/api/discussion/voices/{draft.pk}/').status_code == 204
    draft.refresh_from_db()
    assert (draft.state, draft.file_name) == (State.ERASED, '') and not store.path_of('voices', name).exists()
    picture = Picture.objects.create(owner=writer, width=1, height=1)
    assert errors(signed_in(api, reader).delete(f'/api/discussion/pictures/{picture.pk}/')) == (
        404, [('pictures', 'not_found')])
    assert signed_in(api, writer).delete(f'/api/discussion/pictures/{picture.pk}/').status_code == 204
    assert Picture.objects.get(pk=picture.pk).state == State.ERASED


def test_a_reports_moment_is_a_time_inside_the_voice(api, writer, reader, staff):
    place = Discussion.objects.create(path=PATH, text_path=PATH)
    clip = Clip.objects.create(owner=writer, state=State.LIVE, duration_ms=2000, size=4)
    spoken = Contribution.objects.create(discussion=place, author=writer, kind='post', title='صوت', clip=clip)
    written = Contribution.objects.create(discussion=place, author=writer, kind='post', title='كلام', body='كلام')
    api = signed_in(api, reader)

    def report(c, moment, details='', who=reader):
        return signed_in(api, who).post(f'/api/discussion/contributions/{c.pk}/report/',
                                        {'reason': 'abuse', 'moment_ms': moment, 'details': details}, format='json')

    for c, moment in ((spoken, 'soon'), (spoken, 2001), (spoken, -1), (written, 500)):
        assert errors(report(c, moment)) == (400, [('moment_ms', 'invalid')]), moment
    assert report(spoken, 2000, '  سب فالأخير  ').status_code == 201
    assert report(spoken, 0, 'ت' * (NOTE_MAX + 5), make_user('other-reader')).status_code == 201
    assert list(Report.objects.order_by('pk').values_list('reporter__username', 'contribution', 'reason', 'details',
                                                          'moment_ms')) == [
        ('hamid', spoken.pk, 'abuse', 'سب فالأخير', 2000), ('other-reader', spoken.pk, 'abuse', 'ت' * NOTE_MAX, 0)]
    card = signed_in(api, staff).get('/api/discussion/review/', {'tab': 'reported'}).json()['items'][0]
    assert card['reports']['moments'] == [2000, 0] and card['voice']['duration_ms'] == 2000
    # The same reader asking for it to go, as the person it is about, has said their word already.
    r = signed_in(api, reader).post(f'/api/discussion/contributions/{spoken.pk}/takedown/', {'details': 'أنا هذا'},
                                    format='json')
    assert errors(r) == (409, [('report', 'already')]) and Report.objects.count() == 2


def test_a_takedown_is_asked_of_what_readers_see_or_what_reports_hid(api, writer, reader):
    place = Discussion.objects.create(path=PATH, text_path=PATH)
    now = timezone.now()

    def made(**state):
        return Contribution.objects.create(discussion=place, author=writer, kind='post', title='منشور', body='.',
                                           **state)

    def takedown(c, details='هذا أنا', contact=''):
        return api.post(f'/api/discussion/contributions/{c.pk}/takedown/', {'details': details, 'contact': contact},
                        format='json')

    shown, hidden = made(), made(held_at=now, hidden_at=now)
    for c in (made(erased_at=now), made(removed_at=now), made(held_at=now)):
        assert errors(takedown(c)) == (404, [('contribution', 'not_found')])
    assert errors(takedown(shown, details='   ')) == (400, [('details', 'required')])
    assert takedown(hidden, '  هذا أنا  ', ' 0600000000 ').status_code == 201
    assert signed_in(api, reader).post(f'/api/discussion/contributions/{shown.pk}/takedown/',
                                       {'details': 'د' * (NOTE_MAX + 5), 'contact': 'ب' * 205},
                                       format='json').status_code == 201
    assert list(Report.objects.order_by('pk').values_list('contribution', 'reporter', 'reason', 'takedown', 'details',
                                                          'contact')) == [
        (hidden.pk, None, 'exposing', True, 'هذا أنا', '0600000000'),
        (shown.pk, reader.pk, 'exposing', True, 'د' * NOTE_MAX, 'ب' * 200)]
    # Someone else asking for the same post: their own request; the same person twice: said already.
    other = make_user('ali')
    assert signed_in(api, other).post(f'/api/discussion/contributions/{shown.pk}/takedown/', {'details': 'أنا'},
                                      format='json').status_code == 201
    r = signed_in(api, reader).post(f'/api/discussion/contributions/{shown.pk}/takedown/', {'details': 'مرة أخرى'},
                                    format='json')
    assert errors(r) == (409, [('report', 'already')])
    assert list(Report.objects.filter(contribution=shown).order_by('pk').values_list('reporter', flat=True)) == [
        reader.pk, other.pk]


def test_a_useful_counts_from_an_account_proven_and_three_days_old_to_the_second(api, writer, monkeypatch):
    from apps.discussion.services.gates import VOTE_AFTER_DAYS

    moment = timezone.now()
    monkeypatch.setattr(timezone, 'now', lambda: moment)           # the clock held still
    q = write(api, writer).json()
    voters = {}
    for name, joined, proven in (('on_the_day', timedelta(days=VOTE_AFTER_DAYS), True),
                                 ('a_second_late', timedelta(days=VOTE_AFTER_DAYS) - timedelta(seconds=1), True),
                                 ('unproven', timedelta(days=30), False)):
        voters[name] = make_user(name, proven=proven)
        User.objects.filter(pk=voters[name].pk).update(date_joined=moment - joined,
                                                        email_proven_at=moment - joined if proven else None)
        voters[name].refresh_from_db()
        assert signed_in(api, voters[name]).post(f'/api/discussion/contributions/{q["id"]}/useful/').status_code == 200
    counted = dict(Useful.objects.filter(contribution_id=q['id']).values_list('user__username', 'counted'))
    assert counted == {'on_the_day': True, 'a_second_late': False, 'unproven': False}
    assert Contribution.objects.get(pk=q['id']).useful_count == 1 and points.total(writer) == 1


def test_a_held_voice_is_heard_by_the_moderators_of_its_place_only(api, writer, reader, staff):
    place = Discussion.objects.create(path=PATH, text_path=PATH)
    clip = Clip.objects.create(owner=writer, state=State.EVIDENCE, duration_ms=2000, size=4)
    Contribution.objects.create(discussion=place, author=writer, kind='post', title='صوت', clip=clip,
                                held_at=timezone.now(), held_reasons=['phone'])
    here, elsewhere = make_user('here'), make_user('elsewhere')
    review.appoint(staff, here, [PATH])
    review.appoint(staff, elsewhere, ['/talk/work'])
    assert signed_in(api, here).get(f'/api/discussion/voices/{clip.pk}/').status_code == 200
    for user in (elsewhere, reader):
        assert errors(signed_in(api, user).get(f'/api/discussion/voices/{clip.pk}/')) == (404, [('voice', 'not_found')])


@pytest.fixture
def model(settings, monkeypatch, tmp_path):
    """The check on, with the `anthropic` client's stand-in answering by markers in the words."""
    def answer(custom_id, params):
        words = params['messages'][0]['content']
        if '[unreadable]' in words:
            return 'sorry, I cannot help with that'
        return {'outcome': 'return', 'rule': 'shouting'} if '[odd]' in words else {'outcome': 'publish', 'rule': 'none'}

    claude.install(monkeypatch, settings, tmp_path, answer)
    settings.DISCUSSION_CHECK, settings.LLM_MODELS_ALLOWED = 'model', 'claude-haiku-5-5'


def test_an_answer_the_check_cannot_read_waits_for_a_person_and_an_unknown_rule_holds(api, writer, model):
    r = write(api, writer, consent=True, body='سؤال [unreadable]').json()
    assert (r['held'], r['held_reasons']) == (True, ['check_unavailable'])
    row = Check.objects.get(contribution_id=r['id'])
    assert (row.outcome, row.failure, row.input_tokens, row.output_tokens) == ('unavailable', 'error', 2000, 400)
    r = write(api, writer, body='سؤال [odd]').json()        # «return» under no rule of the site's: a person decides
    assert (r['held'], r['held_reasons']) == (True, ['check'])
    assert (Check.objects.get(contribution_id=r['id']).outcome, Check.objects.get(contribution_id=r['id']).rule) == (
        'hold', '')
    assert write(api, writer, body='سؤال عادي').json()['held'] is False


def test_the_markers_stand_in_failing_as_the_model_can(api, writer, settings):
    settings.DISCUSSION_CHECK, settings.DEBUG = 'markers', True
    r = write(api, writer, consent=True, body='سؤال [boom]').json()
    assert r['held_reasons'] == ['check_unavailable']
    assert (Check.objects.get().model, Check.objects.get().failure) == ('markers', 'error')


def test_the_moderators_median_wait_is_the_middle_one(api, staff, lease):
    place = Discussion.objects.create(path=PATH, text_path=PATH)
    now = timezone.now()
    for hours in (9, 2, 4):
        c = Contribution.objects.create(discussion=place, author=make_user(f'a{hours}'), kind='post', title='منشور',
                                        body='كلام', held_at=now, held_reasons=['phone'])
        Contribution.objects.filter(pk=c.pk).update(created_at=now - timedelta(hours=hours, minutes=1))
        signed_in(api, staff).post(f'/api/discussion/review/contributions/{c.pk}/', {'act': 'approve'}, format='json')
    assert signed_in(api, staff).get('/api/discussion/review/').json()['median_hours'] == 4.0
    c = Contribution.objects.create(discussion=place, author=make_user('a6'), kind='post', title='منشور', body='كلام',
                                    held_at=now, held_reasons=['phone'])
    Contribution.objects.filter(pk=c.pk).update(created_at=now - timedelta(hours=6, minutes=1))
    signed_in(api, staff).post(f'/api/discussion/review/contributions/{c.pk}/', {'act': 'approve'}, format='json')
    assert signed_in(api, staff).get('/api/discussion/review/').json()['median_hours'] == 5.0


def test_a_closed_discussion_says_so_to_the_form(api, lease, reader, settings):
    settings.DISCUSSION_OPEN = False
    writing = signed_in(api, reader).get('/api/discussion/feed/', {'place': PATH}).json()['writing']
    assert writing == {'can': False, 'why': 'discussion.closed', 'voice': False, 'pictures': False}


def test_a_bulletin_issue_and_a_text_held_whole_become_links_a_text_known_by_number_alone_does_not(api, writer):
    held = Text.objects.create(akn_uri='/akn/ma/act/loi/31-08', type='law', number='31-08', title_ar='قانون حماية المستهلك')
    Version.objects.create(text=held, language='ar', valid_from=date(2011, 4, 7), consolidation=Consolidation.AS_PUBLISHED)
    Text.objects.create(akn_uri='/akn/ma/act/loi/1-20', type='law', number='1-20', title_ar='قانون لم تقرأ صيغته')
    body = 'راجع الجريدة الرسمية عدد 6208 والقانون رقم 31.08 والقانون رقم 1.20 والقانون رقم 99.99'
    c = Contribution.objects.get(pk=write(api, writer, body=body).json()['id'])
    issue = Issue.objects.get(number=6208)
    assert [(body[x['start']:x['end']], x['path']) for x in c.links] == [
        ('الجريدة الرسمية عدد 6208', f'/bo/{issue.edition}/6208'), ('والقانون رقم 31.08', '/ma/loi/31-08')]


def test_a_redacted_comment_reads_a_bare_article_in_the_text_its_post_started_from(api, writer, other, staff):
    q = write(api, writer, about=ARTICLE).json()
    words = 'شوف المادة 32 وعيط ليا 0600000000'
    for gone in (False, True):
        if gone:                            # the post's article gone: a bare article names nothing
            Article.objects.filter(eid='art_34').delete()
        held = write(api, other, parent=q['id'], body=words).json()
        assert held['held_reasons'] == ['phone']
        start = words.index('0600000000')
        r = signed_in(api, staff).post(f'/api/discussion/review/contributions/{held["id"]}/',
                                       {'act': 'redact', 'spans': [[start, start + 10]]}, format='json')
        assert r.status_code == 200
        row = Contribution.objects.get(pk=held['id'])
        assert row.body == 'شوف المادة 32 وعيط ليا [حُذف]' and row.published
        assert [x['path'] for x in row.links] == ([] if gone else ['/ma/loi/2013/67-12/art_32'])


def test_a_link_with_someone_in_it_is_never_an_official_one(api):
    def held(body):
        return api.post('/api/discussion/check/', {'body': body}, format='json').json()['reasons']

    assert held('شوف https://www.justice.gov.ma/x') == []
    assert held('شوف https://:@www.justice.gov.ma/x') == ['link']
