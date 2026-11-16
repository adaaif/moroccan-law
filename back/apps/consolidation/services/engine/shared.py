"""What the stages share: the states a change is shown as fact in, and an article found by its number as either
source may print it («7-1» or «1-7»)."""
from apps.consolidation.models import Change
from apps.consolidation.services.instructions.labels import label_key
from apps.corpus.models import Article

SHOWN = (Change.State.CHECKED, Change.State.CONFIRMED, Change.State.READ)


def variants(key: str) -> list[str]:
    """An inserted article's number as either source may print it: «7-1» is also «1-7» (the OCR reads the
    digits of «7.1» in either order)."""
    out = [key]
    parts = key.split('-')
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        out.append(f'{parts[1]}-{parts[0]}')
    return out


def by_key(articles) -> dict[str, Article]:
    out: dict[str, Article] = {}
    for a in articles:
        out.setdefault(label_key(a.label) or a.number, a)
    return out


def pick(table: dict, key: str):
    return next((table[k] for k in variants(key) if k in table), None)
