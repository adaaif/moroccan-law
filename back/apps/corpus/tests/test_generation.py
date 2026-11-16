"""Answers kept by what they depend on (S14 of the performance audit): with a cache that keeps, an answer is worked
out once a generation, `forget_answers` starts a new one, an answer too large is never kept; when Redis does not
answer or refuses to keep more, every answer is still worked out and served."""
import re
from io import StringIO

import pytest
from django.core.cache.backends.base import BaseCache
from django.core.cache.backends.locmem import LocMemCache
from django.core.management import call_command

from apps.corpus.services import generation

KEEPS = {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'answers-kept'}


class Down(BaseCache):
    """Redis not answering: every call raises, as the client does when the connection is refused."""

    def __init__(self, location, params):
        super().__init__(params)

    def _refuse(self, *args, **kwargs):
        raise ConnectionError('Error 111 connecting to 127.0.0.1:6381. Connection refused.')

    get = get_many = add = set = set_many = _refuse


class Full(LocMemCache):
    """Redis at its memory ceiling: it reads, and refuses every new answer («OOM command not allowed»)."""

    def set(self, key, *args, **kwargs):
        if key.startswith('a:'):
            raise ConnectionError('OOM command not allowed when used memory > maxmemory')
        return super().set(key, *args, **kwargs)

    def set_many(self, data, *args, **kwargs):
        raise ConnectionError('OOM command not allowed when used memory > maxmemory')


@pytest.fixture
def caches_as(settings):
    def use(answers):
        settings.CACHES = {**settings.CACHES, 'answers': answers}
    return use


def counting(value):
    made = []

    def build():
        made.append(1)
        return value
    return build, made


def test_an_answer_is_worked_out_once_a_generation_and_forget_answers_starts_another(caches_as):
    caches_as(KEEPS)
    build, made = counting({'n': 1})
    assert generation.kept(['issues'], build) == {'n': 1} and generation.kept(['issues'], build) == {'n': 1}
    assert len(made) == 1
    out = StringIO()
    call_command('forget_answers', 'corpus', stdout=out)
    assert out.getvalue() == 'forgotten: corpus\n'
    generation.kept(['issues'], build)
    assert len(made) == 2
    # Another scope's generation does not touch it; an answer made of both is worked out again.
    both, made_of_both = counting({'n': 2})
    generation.kept(['feed'], both, scopes=('corpus', 'talk'))
    call_command('forget_answers', 'talk', stdout=StringIO())
    generation.kept(['issues'], build)
    generation.kept(['feed'], both, scopes=('corpus', 'talk'))
    assert len(made) == 2 and len(made_of_both) == 2
    call_command('forget_answers', stdout=out)
    assert out.getvalue().endswith('forgotten: corpus, talk, explain\n')


def test_an_answer_past_the_ceiling_is_worked_out_each_time(caches_as, settings):
    caches_as(KEEPS)
    settings.ANSWERS_KEPT_MOST = 10
    build, made = counting({'words': 'x' * 20})
    first = generation.answer(['big'], build)
    assert re.fullmatch(r'"[0-9a-f]{16}"', first['ETag']) and first.content == b'{"words":"xxxxxxxxxxxxxxxxxxxx"}'
    generation.answer(['big'], build)
    assert len(made) == 2
    small, made = counting({'n': 1})
    generation.answer(['small'], small)
    again = generation.answer(['small'], small)
    assert len(made) == 1 and again['ETag'] != first['ETag']          # kept under its own key


def test_many_answers_are_read_together_and_only_the_missing_built(caches_as):
    caches_as(KEEPS)
    asked = []

    def build(names):
        asked.append(sorted(names))
        return {name: name.upper() for name in names}
    assert generation.kept_many(['a', 'b', 'a'], build) == {'a': 'A', 'b': 'B'}
    assert generation.kept_many(['b', 'c'], build) == {'b': 'B', 'c': 'C'}
    assert asked == [['a', 'b'], ['c']]


@pytest.mark.django_db
def test_without_redis_every_answer_is_worked_out_and_served(caches_as, api):
    caches_as({'BACKEND': f'{__name__}.Down'})
    assert generation.current('corpus') is None
    generation.bump('corpus')                                   # says nothing, raises nothing
    build, made = counting({'n': 1})
    generation.kept(['x'], build)
    generation.kept(['x'], build)
    assert len(made) == 2
    assert generation.kept_many(['a'], lambda names: dict.fromkeys(names, 1)) == {'a': 1}
    assert 'ETag' not in generation.answer(['y'], build)
    r = api.get('/api/corpus/issues/')
    assert r.status_code == 200 and r.json() == []


def test_a_cache_that_refuses_to_keep_more_still_serves_the_answer(caches_as):
    caches_as({'BACKEND': f'{__name__}.Full', 'LOCATION': 'answers-full'})
    build, made = counting({'n': 1})
    assert generation.kept(['x'], build) == {'n': 1} and generation.kept(['x'], build) == {'n': 1}
    assert len(made) == 2
    assert generation.kept_many(['a', 'b'], lambda names: {n: n for n in names}) == {'a': 'a', 'b': 'b'}


def test_files_say_when_they_last_changed(tmp_path):
    here = tmp_path / 'a.json'
    here.write_text('{}')
    stamp = generation.files(here, tmp_path / 'gone.json')
    assert stamp.endswith(':-') and stamp.split(':')[0] == str(here.stat().st_mtime_ns)
