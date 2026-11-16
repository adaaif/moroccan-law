"""The registry's rules (apps/analytics/registry.py): every measure answers a question and serves a decision, is renewed or
removed by its day, and carries only properties of the four bounded kinds."""
import math
import re
from datetime import date

import pytest
from django.utils import timezone

from apps.analytics import registry
from apps.analytics.models import DayCount, Event
from apps.analytics.registry import Bool, Choice, Number, Pattern
from apps.analytics.services import sources


def test_no_measure_is_past_its_day():
    """The growth rule: a measure whose day has passed fails here until it is renewed (its question still asked) or
    removed, so the list never keeps a measure nobody reads."""
    assert registry.expired(timezone.localdate()) == [], 'renew these measures (a new expires) or remove them'


def test_a_measure_is_expired_only_after_its_day():
    assert registry.expired(date(2027, 5, 16)) == []
    assert registry.expired(date(2027, 5, 17)) == list(registry.MEASURES)


@pytest.mark.parametrize('name', list(registry.MEASURES))
def test_every_measure_says_what_it_asks_what_it_decides_who_renews_it_and_its_day(name):
    measure = registry.MEASURES[name]
    assert measure.question.endswith('?') and len(measure.question) > 15
    assert measure.decides and measure.owner
    assert measure.category in registry.CATEGORIES
    assert date.fromisoformat(measure.expires) > date(2026, 11, 15)
    assert re.fullmatch(r'[a-z]+\.[a-z]+', name) and len(name) <= Event._meta.get_field('name').max_length


@pytest.mark.parametrize('name', list(registry.MEASURES))
def test_every_property_is_one_of_the_four_bounded_kinds(name):
    """No other kind exists: a free string would let a reader's words in."""
    for prop, rule in registry.MEASURES[name].props.items():
        assert type(rule) in registry.PROP_TYPES, (name, prop)
        assert re.fullmatch(r'[a-z]+', prop), (name, prop)
        # What the fold names after it fits its column.
        assert len(f'{name}.{prop}') <= DayCount._meta.get_field('metric').max_length


def test_the_kinds_languages_and_screens_fit_their_columns():
    for values, field in ((registry.KINDS, 'kind'), (registry.LANGS, 'lang'), (registry.SCREENS, 'screen')):
        assert len(set(values)) == len(values)
        assert max(map(len, values)) <= Event._meta.get_field(field).max_length


def test_the_properties_only_a_first_page_carries_are_page_shown_s():
    assert set(registry.ENTRY_ONLY) <= set(registry.MEASURES['page.shown'].props)


def test_a_choice_is_one_of_its_words():
    rule = Choice('a', 'b', '')
    assert rule.valid('a') and rule.valid('') and not rule.valid('c') and not rule.valid(None) and not rule.valid(1)
    assert rule.ts() == "'a' | 'b' | ''"


def test_a_bool_is_true_or_false_and_nothing_like_it():
    rule = Bool()
    assert rule.valid(True) and rule.valid(False)
    assert not any(rule.valid(v) for v in (1, 0, 'true', None))


def test_a_number_is_refused_out_of_its_range_and_kept_rounded_to_its_step():
    ms, cls, status = Number(0, 60000, 50), Number(0, 5, 0.01), Number(0, 599, 1)
    assert ms.clean(1234) == 1250 and ms.clean(1224.9) == 1200 and ms.clean(59999) == 60000
    assert ms.clean(25) == 50 and ms.clean(125) == 150 and ms.clean(0) == 0     # a half goes up, never to the even band
    assert isinstance(ms.clean(1234.5), int)
    assert cls.clean(0.123) == 0.12 and cls.clean(0.125) == 0.13 and cls.clean(4.999) == 5
    assert isinstance(cls.clean(0.1), float)
    assert status.clean(404.0) == 404 and isinstance(status.clean(404.0), int)
    for wrong in (-1, 60001, math.nan, math.inf, True, '1200', None, [1]):
        assert not ms.valid(wrong), wrong
    assert ms.valid(0) and ms.valid(60000) and ms.valid(12.5)


def test_a_pattern_leaves_no_room_for_words():
    host = registry.MEASURES['page.shown'].props['ref']
    assert host.valid('www.google.co.ma') and host.valid('WWW.Google.CO.MA') and host.clean('L.Facebook.com') == 'l.facebook.com'
    for wrong in ('google', 'google.com/search?q=x', 'a b.com', 'قانون.com', 'x' * 57 + '.com', '', 'https://x.com', 5):
        assert not host.valid(wrong), wrong
    error = registry.MEASURES['app.error'].props['error']
    assert error.valid('TypeError') and not error.valid('TypeError: x is undefined') and not error.valid('x' * 41)
    at = registry.MEASURES['app.error'].props['at']
    assert at.valid('/assets/index-C3x9.js:1:20431') and not at.valid('index.js:1') and not at.valid('a b.js:1:2')
    endpoint = registry.MEASURES['api.failed'].props['endpoint']
    assert endpoint.valid('/api/corpus/at/') and not endpoint.valid('/api/search/?q=x') and not endpoint.valid('api/x')
    assert not Pattern(r'^[a-z]+$', 3).valid('abcd')


def test_an_address_is_the_apps_own_without_query_or_strange_letters():
    path = re.compile(registry.PATH)
    for good in ('/', '/ma/loi/65-99/art_53', '/topics/road/tools/fine', '/bo/general_ar/7533'):
        assert path.fullmatch(good), good
    for bad in ('', 'ma/loi', '/search?q=x', '/a b', '/%D9%82', '/ق', '/' + 'x' * 200, '/x#y'):
        assert not path.fullmatch(bad), bad


def test_the_list_for_privacy_names_each_measure_its_category_and_properties(settings):
    settings.ANALYTICS_DAYS = 30
    shown = registry.public()
    assert shown['days'] == 30
    assert [m['name'] for m in shown['measures']] == list(registry.MEASURES)
    assert shown['measures'][0] == {'name': 'page.shown', 'category': 'interaction',
                                    'props': ['entry', 'source', 'ref', 'back', 'fresh', 'installed']}


@pytest.mark.parametrize('ref, source', [
    (None, 'direct'), ('', 'direct'),
    ('www.google.com', 'search'), ('www.google.co.ma', 'search'), ('google.fr', 'search'), ('www.bing.com', 'search'),
    ('duckduckgo.com', 'search'), ('r.search.yahoo.com', 'search'), ('search.brave.com', 'search'),
    ('com.google.android.googlequicksearchbox', 'search'),
    ('chatgpt.com', 'assistant'), ('claude.ai', 'assistant'), ('www.perplexity.ai', 'assistant'),
    ('gemini.google.com', 'assistant'), ('copilot.microsoft.com', 'assistant'),
    ('l.facebook.com', 'social'), ('m.facebook.com', 'social'), ('www.instagram.com', 'social'), ('t.co', 'social'),
    ('x.com', 'social'), ('web.whatsapp.com', 'social'), ('www.youtube.com', 'social'), ('www.tiktok.com', 'social'),
    ('t.me', 'social'), ('com.whatsapp', 'social'), ('www.linkedin.com', 'social'),
    ('mail.google.com', 'site'), ('hespress.com', 'site'), ('www.sgg.gov.ma', 'site'), ('notgoogle.com', 'site'),
])
def test_a_first_pages_source_is_read_from_the_host_it_came_from(ref, source):
    assert sources.of(ref) == source
