from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.discussion.models import Contribution, Discussion
from apps.sources.models import Edition, Issue

ART_34 = ('تحدد نسبة الزيادة في الوجيبة الكرائية في %8 بالنسبة للمحلات المعدة للسكنى و%10 بالنسبة للمحلات المعدة '
          'للاستعمال المهني.')


@pytest.fixture(autouse=True)
def uploads(settings, tmp_path):
    settings.UPLOADS_DIR = tmp_path / 'uploads'
    return settings.UPLOADS_DIR


@pytest.fixture
def lease():
    """Law 67.12, the housing lease, four of its articles."""
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=6208, date=date(2013, 11, 28))
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/2013/67-12', type='law', number='67-12',
                               number_as_printed='67.12', title_ar='القانون رقم 67.12 المتعلق بتنظيم العلاقات '
                               'التعاقدية بين المكري والمكتري للمحلات المعدة للسكنى أو للاستعمال المهني',
                               first_published_in=issue)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2013, 11, 28),
                               consolidation=Consolidation.AS_PUBLISHED)
    bodies = {
        '32': 'لا يجوز الاتفاق على رفع الوجيبة الكرائية خلال مدة تقل عن ثلاث سنوات من تاريخ إبرام العقد.',
        '33': 'يمكن مراجعة الوجيبة الكرائية كل ثلاث سنوات.',
        '34': ART_34,
        '35': 'إذا كانت الوجيبة الكرائية لا تتجاوز أربعمائة درهم شهريا، فللمحكمة أن تحدد نسبة الزيادة.',
    }
    for i, (n, body) in enumerate(bodies.items()):
        Article.objects.create(version=v, order=i + 1, label=f'المادة {n}', number=n, eid=f'art_{n}', body=body,
                               printed_page=10 + i)
    return text


# Where people write (29 Oct 2026): a topic's place; and the article a post may start from or cite.
PATH = '/talk/housing'
ARTICLE = '/ma/loi/2013/67-12/art_34'
TITLE = 'الزيادة في الكراء'


def make_user(name, *, proven=True, days=30, staff=False):
    user = User.objects.create_user(username=name, email=f'{name}@example.org', password='a long secret 2026',
                                    is_staff=staff)
    user.date_joined = timezone.now() - timedelta(days=days)
    user.email_proven_at = timezone.now() - timedelta(days=days) if proven else None
    user.save()
    return user


def settle(user, lease, n=3):
    """Gives an account published posts elsewhere (the work topic), so its history is not a newcomer's."""
    d, _ = Discussion.objects.get_or_create(path='/talk/work', defaults={'text_path': '/talk/work'})
    for i in range(n):
        Contribution.objects.create(discussion=d, author=user, kind='post', title=f'منشور {i}', body=f'ملاحظة {i}')
    return user


def feed(api, sort='active', place=PATH):
    return api.get('/api/discussion/feed/', {'place': place, 'sort': sort}).json()


def post_of(api, pk):
    return api.get(f'/api/discussion/posts/{pk}/').json()


@pytest.fixture
def writer(lease):
    return settle(make_user('nadia'), lease)


@pytest.fixture
def reader():
    return make_user('hamid')


@pytest.fixture
def staff():
    return make_user('staff', staff=True)


def signed_in(api, user):
    api.force_authenticate(user)
    return api


class _Answer:
    """What the SDK gives back, as much as the check reads of it."""

    def __init__(self, text='', stop_reason='end_turn'):
        from types import SimpleNamespace

        self.stop_reason = stop_reason
        self.content = [SimpleNamespace(type='text', text=text)]
        self.usage = SimpleNamespace(input_tokens=1200, output_tokens=20, cache_creation_input_tokens=0)


@pytest.fixture
def checking(settings, monkeypatch):
    """The check on, with a model that answers by markers in the words: «[hold:respect]», «[return:privacy]»,
    «[refuse]», «[boom]»; anything else is published. Each call's text is kept in `checking.sent`."""
    import json
    import re

    from apps.discussion.services import check

    settings.DISCUSSION_CHECK = 'model'
    settings.ANTHROPIC_API_KEY = 'sk-ant-test'
    settings.LLM_MODELS_ALLOWED = 'claude-haiku-5-5'
    sent = []

    def answer(text):
        sent.append(text)
        if '[boom]' in text:
            raise RuntimeError('the API is down')
        if '[refuse]' in text:
            return _Answer(stop_reason='refusal')
        found = re.search(r'\[(hold|return):(\w+)\]', text)
        outcome, rule = found.groups() if found else ('publish', 'none')
        return _Answer(json.dumps({'outcome': outcome, 'rule': rule}))

    monkeypatch.setattr(check, '_call', answer)
    answer.sent = sent
    return answer
