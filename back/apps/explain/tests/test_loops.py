"""An explanation's sources are checked at one cost whatever their number (no query inside a loop): the articles in
three queries, the texts in one, and the answer is what checking each alone gave."""
from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.services.refusals import Refused
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.discussion.tests.conftest import ARTICLE as PATH, lease, make_user, uploads  # noqa: F401  (fixtures)
from apps.explain.models import Explanation
from apps.explain.services import explanations

pytestmark = pytest.mark.django_db
TEXT = '/ma/loi/2013/67-12'


@pytest.fixture
def sources(lease):
    """Twelve articles of the lease law and twelve laws of their own to cite."""
    version = lease.latest_version()
    for n in range(100, 112):
        Article.objects.create(version=version, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}', body='نص.')
    for n in range(12):
        text = Text.objects.create(akn_uri=f'/akn/ma/act/loi/2020/{n}-20', type='law', number=f'{n}-20', title_ar='قانون')
        Version.objects.create(text=text, language='ar', valid_from=date(2020, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    articles = [f'{TEXT}/art_{n}' for n in range(100, 112)]
    texts = [f'/ma/loi/2020/{n}-20' for n in range(12)]
    return articles, texts


def asked(call) -> int:
    with CaptureQueriesContext(connection) as queries:
        call()
    return len(queries)


def test_twelve_sources_cost_what_one_does(sources):
    articles, texts = sources
    writer = make_user('nadia')
    costs = []
    for register, n in (('ar', 1), ('fr', 6)):
        given = [*articles[:n], *texts[:n]]
        costs.append(asked(lambda: explanations.save(writer, PATH, register, 'شرح المادة', sources=given)))  # noqa: B023 (called in this iteration)
        assert Explanation.objects.get(path=PATH, register=register).pending.sources == given
    assert costs[0] == costs[1], costs


@pytest.mark.parametrize('wrong', ['/ma/loi/2013/67-12/art_99', '/ma/loi/2099/1-99', '/words/kira', '/elsewhere'])
def test_one_source_the_corpus_does_not_hold_refuses_them_all(sources, wrong):
    articles, texts = sources
    with pytest.raises(Refused) as no:
        explanations.save(make_user('nadia'), PATH, 'ar', 'شرح', sources=[*articles[:3], wrong, *texts[:3]])
    assert (no.value.field, no.value.code) == ('sources', 'not_found')
