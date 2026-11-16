"""A post's title, words and author leave the server only where this reader may read the post: every endpoint that
names a post, walked through the states that take it out of sight (held, hidden, removed, deleted) and «بدون اسم».
A title is often what held the post: a name, a phone number."""
import json

import pytest
from django.utils import timezone

from apps.accounts.services import mail
from apps.discussion.models import Cite, Contribution, Discussion, Follow
from apps.discussion.services import counters, thread

from .conftest import ARTICLE, make_user

pytestmark = pytest.mark.django_db
PLACE = '/talk/housing'
SECRET = 'شقة للبيع عند فلان 0600000000'
WORDS = 'كلام لا يقرؤه إلا صاحبه'
STATES = {
    'held': {'held_reasons': ['phone']},
    'hidden': {},
    'removed': {'removed_rule': 'privacy'},
    'deleted': {},
}


@pytest.fixture
def scene(lease):
    d = Discussion.objects.create(path=PLACE, text_path=PLACE)
    author, commenter, stranger = make_user('author-q1'), make_user('commenter-q1'), make_user('stranger-q1')
    post = Contribution.objects.create(discussion=d, author=author, kind='question', title=SECRET, body=WORDS)
    comment = Contribution.objects.create(discussion=d, author=commenter, kind='comment', parent=post,
                                          body='جواب عادي على السؤال')
    Cite.objects.create(contribution=post, path=ARTICLE, text_path='/ma/loi/2013/67-12')
    counters.around(comment)
    # The stranger followed it while it was published.
    Follow.objects.create(user=stranger, path=f'{PLACE}/{post.pk}')
    return {'post': post, 'comment': comment, 'author': author, 'commenter': commenter, 'stranger': stranger}


def put(post: Contribution, state: str) -> None:
    now = timezone.now()
    field = {'held': 'held_at', 'hidden': 'hidden_at', 'removed': 'removed_at', 'deleted': 'deleted_at'}[state]
    Contribution.objects.filter(pk=post.pk).update(**{field: now}, **STATES[state])
    post.refresh_from_db()
    counters.discussion(post.discussion)


def reads(api, s) -> dict[str, str]:
    """What every endpoint that names posts answers this client, as text."""
    post, comment = s['post'], s['comment']
    out = {
        'feed': api.get('/api/discussion/feed/', {'place': PLACE, 'sort': 'new'}),
        'feed-all': api.get('/api/discussion/feed/', {'place': ''}),
        'post': api.get(f'/api/discussion/posts/{post.pk}/'),
        'around': api.get(f'/api/discussion/posts/{post.pk}/replies/', {'around': comment.pk}),
        'places': api.get('/api/discussion/places/'),
        'questions': api.get('/api/discussion/questions/'),
        'answered': api.get('/api/discussion/answered/'),
        'person': api.get(f'/api/discussion/people/{s["commenter"].username}/'),
        'similar': api.post('/api/discussion/similar/', {'path': PLACE, 'q': f'{SECRET} {WORDS}'}, format='json'),
        'cited': api.get('/api/discussion/cited/', {'path': ARTICLE}),
    }
    text = {k: r.content.decode() for k, r in out.items()}
    text['topic'] = json.dumps(thread.topic_talk('housing'), ensure_ascii=False, default=str)
    text['asked-before'] = json.dumps(thread.asked_before(PLACE, f'{SECRET} {WORDS}'), ensure_ascii=False, default=str)
    return text


@pytest.mark.parametrize('state', list(STATES))
def test_a_post_out_of_sight_names_itself_nowhere(api, scene, state):
    put(scene['post'], state)
    for who in (None, scene['stranger']):
        api.force_authenticate(who)
        for name, text in reads(api, scene).items():
            assert SECRET not in text and WORDS not in text, (state, who, name)
    # The stranger's account page: the post they followed, without its title.
    api.force_authenticate(scene['stranger'])
    mine = api.get('/api/discussion/me/').json()
    [followed] = mine['following']
    assert followed['label']['title'] == '' and SECRET not in json.dumps(mine, ensure_ascii=False)
    # A letter's stop page says the topic, never the title.
    token = mail.stop_token(scene['stranger'], f'{PLACE}/{scene["post"].pk}')
    stop = api.get('/api/discussion/letters/stop/', {'t': token}).json()
    assert SECRET not in stop['label']
    # Following it again by its number tells nothing either: refused unless the reader may open the post.
    Follow.objects.all().delete()
    again = api.post('/api/discussion/follow/', {'path': f'{PLACE}/{scene["post"].pk}'}, format='json')
    if state in ('removed', 'deleted'):     # with answers under it, it stands as a marker, with no title
        assert again.status_code == 200
    else:
        assert again.status_code == 404
    assert SECRET not in json.dumps(api.get('/api/discussion/me/').json(), ensure_ascii=False)


@pytest.mark.parametrize('state', ['held', 'hidden'])
def test_its_author_still_reads_their_own_title(api, scene, state):
    put(scene['post'], state)
    api.force_authenticate(scene['author'])
    assert SECRET in api.get(f'/api/discussion/posts/{scene["post"].pk}/').content.decode()
    assert api.post('/api/discussion/follow/', {'path': f'{PLACE}/{scene["post"].pk}'}, format='json').status_code == 200
    labels = {f['path']: f['label']['title'] for f in api.get('/api/discussion/me/').json()['following']}
    assert labels[f'{PLACE}/{scene["post"].pk}'] == SECRET


def test_published_it_is_named_everywhere(api, scene):
    """The same walk on a published post finds the title where it belongs: the walk above tests something."""
    api.force_authenticate(scene['stranger'])
    text = reads(api, scene)
    for name in ('feed', 'feed-all', 'post', 'places', 'answered', 'person', 'cited', 'topic', 'similar'):
        assert SECRET in text[name], name
    assert api.get('/api/discussion/me/').json()['following'][0]['label']['title'] == SECRET


def test_without_a_name_no_list_names_its_author(api, scene):
    Contribution.objects.filter(pk=scene['post'].pk).update(anonymous=True)
    reply = Contribution.objects.create(discussion=scene['post'].discussion, author=scene['stranger'], kind='comment',
                                        parent=scene['post'], reply_to=scene['comment'], body='وأنا أيضا')
    Contribution.objects.filter(pk=scene['comment'].pk).update(anonymous=True)
    counters.around(reply)
    for who in (None, scene['stranger']):
        api.force_authenticate(who)
        for name, text in reads(api, scene).items():
            if name != 'person':            # the commenter's own page names the commenter, never the post's author
                assert 'commenter-q1' not in text, name
            assert 'author-q1' not in text, name


def test_a_reply_never_names_the_author_of_words_out_of_sight(api, scene):
    reply = Contribution.objects.create(discussion=scene['post'].discussion, author=scene['stranger'], kind='comment',
                                        parent=scene['post'], reply_to=scene['comment'], body='وأنا أيضا')
    Contribution.objects.filter(pk=scene['comment'].pk).update(removed_at=timezone.now(), removed_rule='respect')
    counters.around(reply)
    cards = {c['id']: c for c in api.get(f'/api/discussion/posts/{scene["post"].pk}/').json()['post']['replies']}
    assert cards[reply.pk]['reply_to'] == {'id': scene['comment'].pk, 'name': None, 'anonymous': False}


def test_a_held_answer_names_nobody_in_its_notice(api, scene):
    from apps.discussion.models import Notice
    from apps.discussion.services import notices

    Notice.objects.create(user=scene['author'], kind=Notice.Kind.ANSWER, contribution=scene['comment'],
                          path=f'{PLACE}/{scene["post"].pk}')
    assert notices.grouped(scene['author'])[0]['who'] == 'commenter-q1'
    Contribution.objects.filter(pk=scene['comment'].pk).update(held_at=timezone.now())
    assert notices.grouped(scene['author'])[0]['who'] is None


def test_a_reviewer_reads_an_authors_unpublished_words_only_where_they_review(api, scene):
    from apps.discussion.services import review

    staff = make_user('staff-q1', staff=True)
    moderator = make_user('moderator-q1')
    review.appoint(staff, moderator, [PLACE])
    work = Discussion.objects.create(path='/talk/work', text_path='/talk/work')
    Contribution.objects.create(discussion=work, author=scene['author'], kind='post', title='عند المشغل 0600000009',
                                body='كلام', held_at=timezone.now(), held_reasons=['phone'])
    Contribution.objects.filter(pk=scene['post'].pk).update(held_at=timezone.now(), held_reasons=['phone'])
    api.force_authenticate(moderator)
    [card] = api.get('/api/discussion/review/', {'tab': 'held'}).json()['items']
    assert card['id'] == scene['post'].pk and card['context']['recent'] == []
    api.force_authenticate(staff)
    cards = {c['id']: c for c in api.get('/api/discussion/review/', {'tab': 'held'}).json()['items']}
    assert [r['title'] for r in cards[scene['post'].pk]['context']['recent']] == ['عند المشغل 0600000009']
