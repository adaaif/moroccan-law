"""B4 of the search plan: a broken plural meets its singular. The index's stems mapped to their lemma's stem by the
table draft_lemmas wrote from Haiku (CORPUS_DIR/derived/lemmas.json, owner-provisional): an article's `lemma_terms`
and a query's words are mapped the same way, so «عقود» and «عقد», «حقوق» and «حق» meet. Search reads the field only when
SEARCH_LEMMAS is set (until the test set says it helps)."""
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

FILE = 'derived/lemmas.json'


@lru_cache(maxsize=1)
def table() -> dict[str, str]:
    path = Path(settings.CORPUS_DIR) / FILE
    return json.loads(path.read_text())['lemmas'] if path.exists() else {}


def lemmas(terms: list[str]) -> list[str]:
    """Each stem as its lemma's stem (itself when the table has none), in order."""
    t = table()
    return [t.get(term, term) for term in terms]
