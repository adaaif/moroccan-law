"""Answers kept by what they depend on (S14 of the performance audit, 24 Oct 2026).

Most public answers change only when something writes what they are made of, so they are kept in the 'answers' cache
under a key that carries the generation of each thing they read:

- `corpus`: the law, its versions, changes, pages and the budget. manage.py bumps it after every command that may
  write (an issue loaded, a consolidation, corrections, a reload, a migration), and the corrections applied from the
  site bump it too.
- `talk`: the discussion. Every save or delete of a contribution, a vote, a discussion, a point, a badge, an account
  or a voice or picture bumps it (apps.discussion.apps); an answer that holds it is kept a minute at most, since its
  voice links are signed.
- `explain`: the people's explanations, bumped by every save or delete of one, of its history or of its «مفيد».

A generation is a time in nanoseconds, never reused, so a key that carries it is never stale and nothing needs
deleting: the old answers expire. The day is in every key too (the version in force «today», the half year's texts).
Without Redis the 'answers' cache keeps nothing and every answer is worked out; when Redis does not answer, the answer
is worked out and the page says nothing. An answer larger than ANSWERS_KEPT_MOST is worked out each time: a few such
answers would fill the cache. The limits' counts are elsewhere (config/caching.py `counters`): this cache evicts.
"""
import hashlib
import logging
import time
from datetime import date

from django.conf import settings
from django.core.cache import caches
from django.http import HttpResponse
from rest_framework.renderers import JSONRenderer

log = logging.getLogger(__name__)
DAY = 24 * 3600
SCOPES = ('corpus', 'talk', 'explain')


def _answers():
    return caches['answers']


def current(*scopes: str) -> str | None:
    """The present generation of each scope, joined; None when none is kept (no Redis)."""
    cache = _answers()
    try:
        found = cache.get_many([f'gen:{s}' for s in scopes])
        for scope in scopes:
            if f'gen:{scope}' not in found:
                cache.add(f'gen:{scope}', str(time.time_ns()), timeout=None)
                found[f'gen:{scope}'] = cache.get(f'gen:{scope}')
    except Exception:  # no Redis: nothing is kept, everything is worked out
        log.warning('answers cache unavailable', exc_info=True)
        return None
    gens = [found.get(f'gen:{s}') for s in scopes]
    return None if None in gens else '.'.join(gens)


def bump(*scopes: str) -> None:
    """Whatever was kept under these scopes (every scope when none is named) is not served again."""
    try:
        _answers().set_many({f'gen:{s}': str(time.time_ns()) for s in scopes or SCOPES}, timeout=None)
    except Exception:
        log.warning('answers cache unavailable', exc_info=True)


def _key(parts, scopes, gen: str | None = '') -> str | None:
    gen = current(*scopes) if gen == '' else gen
    if gen is None:
        return None
    return 'a:' + hashlib.sha1(':'.join([gen, date.today().isoformat(), *map(str, parts)]).encode(), usedforsecurity=False).hexdigest()


def _kept(key: str | None, build, timeout: int, size=None):
    """The value kept under `key`, else `build()`'s, kept unless it is None (a lookup that found nothing, which a
    caller may ask for under any name) or `size(value)` passes ANSWERS_KEPT_MOST."""
    if key is None:
        return build()
    cache = _answers()
    try:
        found = cache.get(key)
    except Exception:  # noqa: BLE001
        return build()
    if found is None:
        found = build()
        if found is None or (size is not None and size(found) > settings.ANSWERS_KEPT_MOST):
            return found
        try:
            cache.set(key, found, timeout)
        except Exception:  # noqa: BLE001
            pass
    return found


def kept(parts, build, scopes=('corpus',), timeout: int = DAY, size=None):
    """`build()`'s value, kept under `parts` and the scopes' generations; never when `size(value)` passes
    ANSWERS_KEPT_MOST (a drawn page as large as the largest answers)."""
    return _kept(_key(parts, scopes), build, timeout, size)


def kept_many(names: list, build, scopes=('corpus',), timeout: int = DAY) -> dict:
    """{name: value} for many names in one read: the kept ones from the cache, `build(missing)` for the others."""
    gen = current(*scopes)
    keys = {name: _key(['many', name], scopes, gen) for name in dict.fromkeys(names)}
    if None in keys.values():
        return build(list(keys))
    cache = _answers()
    try:
        found = cache.get_many(list(keys.values()))
    except Exception:  # noqa: BLE001
        return build(list(keys))
    out = {name: found[key] for name, key in keys.items() if key in found}
    missing = [name for name in keys if name not in out]
    if missing:
        made = build(missing)
        out.update(made)
        try:
            cache.set_many({keys[name]: value for name, value in made.items()}, timeout)
        except Exception:  # noqa: BLE001
            pass
    return out


def _sent(body: bytes, key: str | None) -> HttpResponse:
    response = HttpResponse(body, content_type='application/json')
    if key is not None:
        response['ETag'] = f'"{key[2:18]}"'
    return response


def answer(parts, build, scopes=('corpus',), timeout: int = DAY) -> HttpResponse:
    """The JSON of `build()` as sent, kept rendered under `parts` and the scopes' generations. Its ETag is its key's (a
    reader who has it gets a 304 and nothing is rendered); without a kept generation Django's content ETag stands."""
    key = _key(parts, scopes)
    return _sent(_kept(key, lambda: JSONRenderer().render(build()), timeout, len), key)


def counted(parts, build, count, scopes=('corpus',), timeout: int = DAY) -> tuple[HttpResponse, int]:
    """`answer`, and what `count(value)` finds in the value when it is built (the articles it carries), kept beside its
    bytes: a metered answer says what it gave without its JSON being read back. Its keys are never `answer`'s."""
    key = _key(['counted', *parts], scopes)

    def made():
        value = build()
        return JSONRenderer().render(value), count(value)
    body, n = _kept(key, made, timeout, lambda kept: len(kept[0]))
    return _sent(body, key), n


def files(*paths) -> str:
    """When files an answer reads were last changed: part of its key."""
    return ':'.join(str(p.stat().st_mtime_ns) if p.exists() else '-' for p in paths)
