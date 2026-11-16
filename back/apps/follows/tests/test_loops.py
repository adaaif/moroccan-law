"""The follows' letters and news cost the same for a few people and addresses as for ten times as many (no query inside
a loop): what each address names, the changes, a topic's, a state's and a commune's newest texts are read once for all
the addresses, and a letter's follows are told in one write."""
from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.consolidation.models import Change
from apps.corpus.models import Text
from apps.discussion.tests.conftest import lease, make_user, uploads  # noqa: F401  (fixtures)
from apps.follows.models import Follow
from apps.follows.services import following, news
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db
TEXT = '/ma/loi/2013/67-12'
COMMUNES = ['سيدي بنور', 'الجديدة', 'أزمور', 'بني ملال', 'خريبكة', 'سطات']


@pytest.fixture
def world(lease):
    """Changes to the lease law's articles, six states or cities each named by a few new texts, six communes each in a
    few land texts, and a new text on renting in the topic's half year."""
    from apps.places.models import Mention, Place
    from apps.topics.models import PlaceText

    for number, by, issue, on in (('34', '2-24', 7547, date(2026, 9, 28)), ('33', '10-26', 7551, date(2026, 10, 12)),
                                  ('', '11-26', 7552, date(2026, 10, 19))):
        Change.objects.create(text_uri=lease.akn_uri, number=number, verb='modified', source=Change.Source.READING,
                              by_kind='law', by_number=by, issue=issue, page=7012, published_on=on, state='read')
    recent = Issue.objects.create(edition=Edition.GENERAL_AR, number=7555, date=timezone.localdate() - timedelta(days=20))
    Text.objects.create(akn_uri='/akn/ma/act/decret/2026/2-26-100', type='decree', number='2-26-100',
                        title_ar='مرسوم بتحديد شروط الكراء', first_published_in=recent)
    for p in range(6):
        place = Place.objects.create(slug=f'city-{p}', kind='city', name_ar=f'مدينة {p}', name_fr=f'Ville {p}')
        for t in range(4):
            uri = f'/akn/ma/act/decret/2026/2-26-{p}{t}'
            Text.objects.get_or_create(akn_uri=uri, defaults={'type': 'decree', 'number': f'2-26-{p}{t}',
                                                              'title_ar': f'مرسوم رقم {p}{t}'})
            for order in (-1, 3):
                Mention.objects.create(place=place, uri=uri, eid='' if order < 0 else 'art_3', order=order,
                                       date=date(2026, 1 + t, 1 + p), issue=str(7500 + t), edition='general_ar',
                                       page=t, text_type='decree', kind='decree', form=place.name_ar)
    for c, commune in enumerate(COMMUNES):
        for t in range(3):
            PlaceText.objects.create(uri=f'/akn/ma/act/decret/2025/2-25-{c}{t}', kind='expropriation',
                                     date=date(2025, 1 + t, 1 + c), issue=str(7400 + t), title=f'مرسوم نزع ملكية {c}{t}',
                                     communes=[commune], search=f'مرسوم نزع ملكيه {c}{t} {fold(commune)}')
    return lease


def fold(words):
    from apps.sources.services.compare import fold as folded
    return folded(words)


def addresses(n: int) -> list[str]:
    """`n` addresses of every kind: the law, its articles, the topics, the states and cities, the communes."""
    kinds = [TEXT, *(f'{TEXT}/art_{a}' for a in (32, 33, 34, 35)), '/topics/housing', '/topics/work',
             *(f'/places/city-{p}' for p in range(6)), *(f'/places/{c}' for c in COMMUNES)]
    return kinds[:n]


def asked(call) -> tuple[list[str], object]:
    with CaptureQueriesContext(connection) as queries:
        out = call()
    return [q['sql'] for q in queries], out


def readers(start: int, end: int, paths: list[str]):
    for i in range(start, end):
        user = make_user(f'reader{i}')
        Follow.objects.bulk_create([Follow(user=user, path=p) for p in paths])


def test_the_letters_read_the_same_whatever_their_readers(world, django_capture_on_commit_callbacks):
    from django.core import mail
    paths = addresses(19)
    costs, letters = [], []
    for start, end in ((0, 3), (3, 30)):
        readers(start, end, paths)
        Follow.objects.update(told=[])
        mail.outbox.clear()
        with django_capture_on_commit_callbacks(execute=True):
            sql, sent = asked(following.send_letters)
        assert sent == end == len(mail.outbox)
        costs.append(sql)
        letters.append(sorted(m.body for m in mail.outbox))
    reads = [[q for q in sql if q.startswith('SELECT')] for sql in costs]
    assert len(reads[0]) == len(reads[1]), [len(r) for r in reads]
    # What stays a write a letter: its readers' follows told, in one statement.
    assert [sum(q.startswith('UPDATE') for q in sql) for sql in costs] == [3, 30]
    body = letters[1][0]
    assert 'مرسوم رقم 53' in body and 'مرسوم نزع ملكية 52' in body and 'القانون رقم 11.26' in body
    told = Follow.objects.filter(user__username='reader29', path='/places/city-5').get().told
    assert told == [f'where:/ma/decret/2026/2-26-5{t}' for t in (3, 2, 1, 0)]


def test_a_devices_news_reads_the_same_whatever_it_follows(world, api):
    """One article, state and commune, then four articles, six states and six communes; the same two topics, each read
    once (the topics are a fixed few)."""
    costs = []
    for articles, places in ((1, 1), (4, 6)):
        paths = [TEXT, *(f'{TEXT}/art_{a}' for a in (32, 33, 34, 35)[:articles]), '/topics/housing', '/topics/work',
                 *(f'/places/city-{p}' for p in range(places)), *(f'/places/{c}' for c in COMMUNES[:places])]
        sql, found = asked(lambda: news.news(paths))  # noqa: B023 (called in this iteration)
        assert [f['path'] for f in found] == paths
        assert all(f['items'] for f in found if f['kind'] in ('text', 'where', 'place') or f['path'] == '/topics/housing')
        costs.append(len(sql))
    assert costs[0] == costs[1], costs
