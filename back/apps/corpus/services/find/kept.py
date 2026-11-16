"""What is kept in the process for a generation of the corpus: the library's books' names and the laws' titles, and
the lookups over them (a book's or a numbered text's address, how many texts cite each, the laws whose title holds
some words)."""
import re
import time

import ma_law
from django.db.models import Count

from apps.corpus.models import Mention, Text
from apps.corpus.services import generation, works
from apps.corpus.services.find.typed import title_stems, words


LAWLIKE = ('law', 'organic_law', 'decree_law', 'constitution', 'bill')
_AMENDS = re.compile(r'بتغيير|بتتميم|بتعديل|يعدل|يغير|يتمم|تغير بموجبه|يغير بمقتضاه|في تغيير|في تتميم|بنسخ|يوافق بموجبه|بنشر|بتعيين|بالمصادقه|تصفيه|المعدل')


_KEPT: dict = {}


def _kept(name: str, build):
    gen = generation.current('corpus') or f'none:{int(time.time() // 300)}'
    if _KEPT.get(name, (None, None))[0] != gen:
        _KEPT[name] = (gen, build())
    return _KEPT[name][1]


def _books() -> dict:
    """{key: {uri, base, names: the stems of each of its names}} for the library's books the site holds."""
    def build():
        from apps.corpus.services import codes
        from apps.corpus.services.library import BOOKS, BRANCHES
        keys = [k for b in BRANCHES for k in ([b[3]] if b[3] else []) + b[4]]
        bases = {b[3] for b in BRANCHES if b[3]}
        extra = {k: BOOKS[k][0] + (BOOKS[k][1], BOOKS[k][2]) for k in keys if BOOKS[k][0] is not None}
        texts = codes.texts_of(keys, extra=extra)
        out = {}
        for key in keys:
            text = texts.get(key)
            if text is None:
                continue
            _, ar, fr, names = BOOKS[key]
            sets = [w for w in (words(n) for n in [ar, fr, *names]) if w]
            out[key] = {'uri': text.akn_uri, 'base': key in bases, 'names': sets}
        return out
    return _kept('books', build)


def _laws() -> list[tuple]:
    """(address, type, title stems as one string, whether the title only amends, status, the day signed) for every law,
    organic law, decree-law, constitution and bill: 2,341 rows on 10 Nov 2026."""
    def build():
        rows = Text.objects.filter(type__in=LAWLIKE).values_list('akn_uri', 'type', 'title_ar', 'number_as_printed', 'status', 'signed_on')
        return [(uri, kind, ' ' + ' '.join(title_stems(title or '') + [ma_law.fold(number or '')]) + ' ', bool(_AMENDS.search(ma_law.fold(title or ''))),
                 status, signed) for uri, kind, title, number, status, signed in rows]
    return _kept('laws', build)


def _address(target) -> str | None:
    """A book's key or (kind, number) → the address the site holds, or None."""
    if isinstance(target, str):
        book = _books().get(target)
        return book['uri'] if book else None
    uri, state = works.resolve(*target)
    return uri if state == 'resolved' else None


def _cited(uris) -> dict[str, int]:
    """How many texts point at each of these (one query): the text a day is known for stands first."""
    uris = list(uris)
    if len(uris) < 2:
        return {}
    return dict(Mention.objects.filter(to_uri__in=uris, state=Mention.State.RESOLVED).values('to_uri')
                .annotate(n=Count('from_uri', distinct=True)).values_list('to_uri', 'n'))


def _titled(wanted: list[str]) -> list[tuple]:
    """The laws whose title holds every word: those that stand and are a text of their own first, then the title that
    says the least beside the words («تنظيم التعليم العالي» before the agency that assesses it), then the newest."""
    if not wanted:
        return []
    found = [row for row in _laws() if all(f' {w}' in row[2] for w in wanted)]
    found.sort(key=lambda r: (r[3], r[4] == 'repealed', r[2].count(' '), -(r[5].toordinal() if r[5] else 0)))
    return found
