"""Every door of the discussion, its pictures and voices, the explanations, the follows, the budget and the list of
corrections has a request limit (OP15 of the open-source audit): none of their reads had one, so one address could ask
them at any rate. A door anyone may open counts by address the public rate (240 a minute an address, the corpus's and
the search's); a door that needs an account counts that account (`account`), so the readers behind one mobile address
never share it."""
from unittest import mock

import pytest
from django.core.cache import cache
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import AllowAny
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.discussion.tests.conftest import PATH, make_user
from apps.opendata.throttles import PublicRate, ScopedRate

pytestmark = pytest.mark.django_db
APPS = ('apps.discussion.', 'apps.media.', 'apps.explain.', 'apps.follows.', 'apps.budget.')


def _views(patterns):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _views(p.url_patterns)
        elif isinstance(p, URLPattern) and isinstance(getattr(p.callback, 'cls', None), type) \
                and issubclass(p.callback.cls, APIView):
            yield p.callback.cls


def _ours():
    from apps.quality.api.views import Corrections
    return {v for v in _views(get_resolver().url_patterns) if v.__module__.startswith(APPS) or v is Corrections}


def test_every_door_has_a_limit():
    views = _ours()
    assert len(views) > 40
    for view in views:
        if AllowAny in view.permission_classes:
            assert any(issubclass(c, PublicRate) for c in view.throttle_classes), view
            if getattr(view, 'throttle_scope', None):
                assert ScopedRate in view.throttle_classes, view        # its own scope too (checks, reports)
        else:
            assert getattr(view, 'throttle_scope', None) and ScopedRate in view.throttle_classes, view


@pytest.fixture
def tight(settings):
    settings.PUBLIC_API_RATES = {'anonymous': '3/min', 'keyed': '3/min'}
    cache.clear()
    with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'account': '3/min'}):
        yield
    cache.clear()


@pytest.mark.parametrize('door', ['/api/discussion/feed/?place=' + PATH, '/api/discussion/places/',
                                  '/api/explain/words/', '/api/follows/news/?path=/ma/loi/65-99',
                                  '/api/budget/laws/', '/api/quality/corrections/'])
def test_an_address_is_held_at_the_public_rate(api, tight, door):
    asked = [api.get(door, REMOTE_ADDR='203.0.113.7', HTTP_X_FORWARDED_FOR='203.0.113.7').status_code
             for _ in range(4)]
    assert asked[:3] == [200] * 3 and asked[3] == 429
    # Another address is not held for it.
    assert api.get(door, REMOTE_ADDR='203.0.113.7', HTTP_X_FORWARDED_FOR='198.51.100.4').status_code == 200


def test_these_doors_count_apart_from_the_laws_own(api, tight):
    """What a page asks of the discussion beside a law never spends the address's allowance for the law."""
    there = dict(REMOTE_ADDR='203.0.113.7', HTTP_X_FORWARDED_FOR='203.0.113.9')
    assert [api.get('/api/discussion/places/', **there).status_code for _ in range(4)][-1] == 429
    assert api.get('/api/corpus/shelf/', **there).status_code == 200


def test_a_door_that_needs_an_account_counts_the_account_not_the_address(api, tight):
    one, other = make_user('salma'), make_user('karim')
    api.force_authenticate(one)
    asked = [api.get('/api/discussion/me/unseen/', HTTP_X_FORWARDED_FOR='203.0.113.7').status_code for _ in range(4)]
    assert asked == [200, 200, 200, 429]
    # The next account behind the same mobile address is not held for what the first asked.
    api.force_authenticate(other)
    assert api.get('/api/discussion/me/unseen/', HTTP_X_FORWARDED_FOR='203.0.113.7').status_code == 200
