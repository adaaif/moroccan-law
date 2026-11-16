"""«النقاش» (R12 of the for-everyone review): questions someone answered come with their answer — the one the asker marked
«أفادني», else the most useful — the latest answered first; the questions' filter names the topics that wait."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.discussion.models import Contribution, Discussion
from apps.discussion.services import counters, thread

from .conftest import PATH, make_user

pytestmark = pytest.mark.django_db


def test_an_answered_question_comes_with_the_answer_that_helped(lease):
    d = Discussion.objects.create(path=PATH, text_path=PATH)
    asker, a, b = make_user('kawtar'), make_user('salma'), make_user('omar')
    q = Contribution.objects.create(discussion=d, author=asker, kind='question', title='العيادة',
                                 body='واش 10% كتطبق على العيادة؟')
    Contribution.objects.create(discussion=d, author=a, kind='explanation', parent=q, body='إيه.', useful_count=5)
    helped = Contribution.objects.create(discussion=d, author=b, kind='explanation', parent=q, body='العيادة محل مهني.',
                                         accepted_at=timezone.now())
    waiting = Contribution.objects.create(discussion=d, author=asker, kind='question', body='وشحال من مرة؟')
    Contribution.objects.filter(pk=waiting.pk).update(created_at=timezone.now() - timedelta(days=1))
    counters.replies(q)         # as the services do after each comment
    out = thread.answered_questions()
    assert [x['id'] for x in out['questions']] == [q.pk]
    assert out['questions'][0]['answer']['id'] == helped.pk


def test_the_questions_filter_names_the_topics_that_wait(lease):
    d = Discussion.objects.create(path=PATH, text_path=PATH, open_questions=1)
    Contribution.objects.create(discussion=d, author=make_user('kawtar'), kind='question', title='سؤال', body='؟')
    out = thread.open_questions()
    assert out['places'] == [PATH] and out['questions'][0]['label']['name']['ar'] == 'السكن والكراء'
