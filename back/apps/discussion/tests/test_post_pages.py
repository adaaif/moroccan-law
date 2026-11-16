"""A post's comments as a tree grown on request (the load test of 30 Oct 2026: a post of 23,428 comments answered 13 MB
at once): its first-level comments a page at a time, each with its first replies, a
door under any comment for the rest of the replies that answer it, and a link to one comment landing on the line of its
conversation down to it; every card says how many answer it."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import Contribution, Discussion
from apps.discussion.services import counters, thread
from apps.discussion.services.thread import comments

from .conftest import make_user

pytestmark = pytest.mark.django_db
PLACE = '/talk/housing'


def post_with_talks(n: int):
    """A question and `n` first-level comments, each answered twice, the older ones first."""
    d = Discussion.objects.create(path=PLACE, text_path=PLACE)
    asker, a, b = make_user('asker'), make_user('salma'), make_user('omar')
    q = Contribution.objects.create(discussion=d, author=asker, kind='question', title='سؤال على الكراء', body='؟')
    start = timezone.now() - timedelta(days=2)
    tops = []
    for i in range(n):
        top = Contribution.objects.create(discussion=d, author=a, kind='comment', parent=q, body=f'تعليق {i}',
                                          useful_count=i)
        Contribution.objects.filter(pk=top.pk).update(created_at=start + timedelta(hours=i))
        for j in range(2):
            Contribution.objects.create(discussion=d, author=b, kind='comment', parent=q, reply_to=top, body=f'جواب {i}.{j}')
        tops.append(top)
    counters.replies(q)         # as the services do after each comment
    return q, tops


def test_a_post_answers_a_page_of_its_first_comments_each_with_its_first_replies(monkeypatch):
    monkeypatch.setattr(comments, 'CONVERSATIONS', 2)
    q, tops = post_with_talks(5)
    first = thread.post(None, q.pk)
    cards = {r['id']: r for r in first['post']['replies']}
    assert len(cards) == 6 and first['conversations'] == 5 and first['next_page'] == 2
    # «best»: the most useful first; each comes with the first that answer it, and says how many do.
    assert next(iter(cards)) == tops[4].pk and {tops[4].pk, tops[3].pk} <= set(cards)
    assert cards[tops[4].pk]['answers'] == 2 and all(r['answers'] == 0 for r in cards.values() if r['reply_to'])
    assert all(r['reply_to'] is None or r['reply_to']['id'] in cards for r in cards.values())
    assert thread.post(None, q.pk, page=3)['next_page'] is None
    assert {r['id'] for r in thread.post(None, q.pk, sort='old')['post']['replies']} >= {tops[0].pk, tops[1].pk}
    assert {r['id'] for r in thread.post(None, q.pk, sort='new')['post']['replies']} >= {tops[4].pk, tops[3].pk}
    seen = set()
    for page in (1, 2, 3):
        seen |= {r['id'] for r in thread.post(None, q.pk, page=page, sort='old')['post']['replies']}
    assert len(seen) == 15                       # every comment, once, over the three pages


def long_talk():
    """One first-level comment answered twice, then ten more: each other one answers the one before it."""
    q, tops = post_with_talks(1)
    top, d, b = tops[0], tops[0].discussion, make_user('nadia')
    start = timezone.now() - timedelta(days=1)
    last, made = top, []
    for i in range(10):
        to = last if i % 2 else top
        last = Contribution.objects.create(discussion=d, author=b, kind='comment', parent=q, reply_to=to, body=f'رد {i}')
        Contribution.objects.filter(pk=last.pk).update(created_at=start + timedelta(minutes=i))
        made.append(last)
    return q, top, made


def test_a_door_brings_the_replies_that_answer_one_comment_a_page_at_a_time(monkeypatch):
    monkeypatch.setattr(comments, 'DOOR', 4)
    q, top, made = long_talk()
    page = {r['id']: r for r in thread.post(None, q.pk)['post']['replies']}
    assert page[top.pk]['answers'] == 7 and len(page) == 1 + thread.REPLY_PREVIEW
    first = thread.post_answers(None, q.pk, top.pk)
    # Only what answers it, oldest first (the first page holds the ones the post's page showed), each with its count.
    assert [r['id'] for r in first['replies']] == [made[0].pk, made[2].pk, made[4].pk, made[6].pk]
    assert first['answers'] == 7 and first['next_page'] == 2 and first['replies'][0]['answers'] == 1
    assert set(page) - {top.pk} <= {r['id'] for r in first['replies']}
    rest = thread.post_answers(None, q.pk, top.pk, page=2)
    assert len(rest['replies']) == 3 and rest['next_page'] is None
    assert [r['id'] for r in thread.post_answers(None, q.pk, made[0].pk)['replies']] == [made[1].pk]
    with pytest.raises(Refused):
        thread.post_answers(None, q.pk, 10 ** 9)


def test_a_link_to_one_comment_lands_on_the_line_of_its_conversation_down_to_it():
    q, top, made = long_talk()
    deep = Contribution.objects.create(discussion=top.discussion, author=q.author, kind='comment', parent=q,
                                       reply_to=made[1], body='وأنا؟')
    Contribution.objects.create(discussion=top.discussion, author=q.author, kind='comment', parent=q, reply_to=deep,
                                body='شكرا')
    around = thread.post_around(None, q.pk, deep.pk)
    ids = [r['id'] for r in around['replies']]
    assert ids[:4] == [top.pk, made[0].pk, made[1].pk, deep.pk] and len(ids) == 5 and around['first'] == top.pk
    cards = {r['id']: r for r in around['replies']}
    assert cards[top.pk]['answers'] == 7 and cards[deep.pk]['answers'] == 1
    with pytest.raises(Refused):
        thread.post_around(None, q.pk, 10 ** 9)


def test_a_question_s_marked_answer_leads_its_comments_by_use_never_by_date():
    # 31 Oct 2026: no box above the comments for the answer; the one its asker marked is marked where it
    # stands, first by «الأنفع» with its replies, and in its place by «الأحدث» or «الأقدم».
    q, tops = post_with_talks(3)
    first = thread.post(None, q.pk)
    assert 'answer' not in first and first['people'] == 2
    Contribution.objects.filter(pk=tops[1].pk).update(accepted_at=timezone.now())
    counters.replies(q)
    ids = {t.pk: i for i, t in enumerate(tops)}

    def order(sort):
        replies = thread.post(None, q.pk, sort=sort)['post']['replies']
        return [ids[r['id']] for r in replies if r['id'] in ids], replies

    best, replies = order('best')
    assert best == [1, 2, 0] and replies[0]['accepted'] and not any(r['accepted'] for r in replies[1:])
    # Its replies come with it.
    assert [r['reply_to']['id'] for r in replies[1:3]] == [tops[1].pk] * 2
    assert order('new')[0] == [2, 1, 0] and order('old')[0] == [0, 1, 2]
    # Held, it leads nothing.
    Contribution.objects.filter(pk=tops[1].pk).update(held_at=timezone.now())
    counters.replies(q)
    assert order('best')[0] == [2, 0]
