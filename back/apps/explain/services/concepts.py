"""The words that open the law (R9 of the for-everyone review): data/concepts.json, and the built-in words of the reading
page, each a page at /words/<slug>."""
import json
from functools import cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / 'data' / 'concepts.json'
# The reading page's own words (web src/features/corpus/article/words.ts): their meaning is in the web's strings.
BUILT_IN = ['bo', 'constitution', 'organic_law', 'law', 'code', 'dahir', 'promulgation', 'decree_law', 'decree', 'order',
            'decision', 'circular', 'convention', 'in_force', 'none_found', 'amended', 'repealed', 'not_yet_in_force', 'as_published',
            'consolidated']


@cache
def load() -> list[dict]:
    return json.loads(DATA.read_text())['concepts']


def find(slug: str) -> dict | None:
    if slug in BUILT_IN:
        return {'slug': slug, 'term': None, 'search': '', 'topic': '', 'built_in': True}
    return next(({**c, 'built_in': False} for c in load() if c['slug'] == slug), None)
