"""Questions asked before, found by the site's own reader (ma_law.search_terms), no model: those of a place sharing a
question's words while it is typed (W3), and those a search's question asked already («سولو قبلك»)."""
from functools import lru_cache

from apps.discussion.models import Contribution, Kind
from apps.discussion.services import counters

# Words too common in a question to say two questions are alike.
_COMMON = set('واش كيف علاش شنو اشنو اش هل ما ماذا لماذا متى اين فين اذا ادا لي اللي ديال عند عندي نقدر يقدر '
              'est que qui quoi comment pourquoi les des une dans pour avec sur pas'.split())


def similar(path: str, words: str, limit: int = 3) -> list[dict]:
    """Questions in the same place that share a question's words (W3): folded and stemmed by the site's own reader
    (ma_law.search_terms), no model; the latest 400 of them. The ones with a marked answer first."""
    import ma_law

    asked = {t for t in ma_law.search_terms(words or '') if len(t) > 1 and t not in _COMMON}
    if len(asked) < 2:
        return []
    found = []
    for c in (Contribution.objects.filter(counters.published(), discussion__path=path, parent=None,
                                          kind=Kind.QUESTION, duplicate_of=None).order_by('-created_at')[:400]):
        theirs = {t for t in ma_law.search_terms(f'{c.title} {c.body}') if t not in _COMMON}
        shared = asked & theirs
        if len(shared) >= 2 and len(shared) / len(asked) >= 0.3:
            found.append((c, len(shared) / len(asked)))
    # Which have a marked answer, from the answers their posts keep, in one query by key; their published comments are
    # their reply_count (reading every comment under them took seconds under a busy post).
    marked = set(Contribution.objects.filter(pk__in=[c.answer_id for c, _ in found if c.answer_id],
                                             accepted_at__isnull=False).values_list('parent_id', flat=True))
    found.sort(key=lambda x: (-(x[0].pk in marked), -x[1], -x[0].useful_count))
    return [{'id': c.pk, 'title': c.title, 'body': c.body[:240], 'path': f'{path}/{c.pk}', 'useful': c.useful_count,
             'answers': c.reply_count, 'accepted': c.pk in marked, 'share': round(share, 2)} for c, share in found[:limit]]


@lru_cache(maxsize=4096)
def _read(said: str) -> tuple[frozenset, frozenset]:
    """A question's words as search reads them, and its runs of words as the doors read them: read once per process,
    not on every search that names its topic."""
    import ma_law

    from apps.topics.services.topics import question_grams

    return frozenset(t for t in ma_law.search_terms(said) if t not in _COMMON), frozenset(question_grams(said))


def asked_before(path: str, words: str, door_words: list[str] = (), limit: int = 3) -> list[dict]:
    """The questions of a topic's place a search's question asked already (the search page's «سولو قبلك», 30 Oct 2026):
    first those whose words name the door the question names («مول الدار بغا يزيد 15% فالكرا» for «طلع ليا الكرا»), then
    those sharing three in four of its words; each with its answer's first lines, the one its post keeps
    (counters.replies: the one its asker marked, else the most useful, else the first; never the asker's own). The site's
    own reader, no model; the latest 400 questions; two queries."""
    import ma_law

    from apps.topics.services.topics import folded

    asked = {t for t in ma_law.search_terms(words or '') if len(t) > 1 and t not in _COMMON}
    door = {folded(w) for w in door_words}
    if len(asked) < 2 and not door:
        return []
    found = []
    for c in (Contribution.objects.filter(counters.published(), discussion__path=path, parent=None,
                                          kind=Kind.QUESTION, duplicate_of=None)
              .only('id', 'title', 'body', 'created_at', 'useful_count', 'author_id', 'reply_count', 'answer_id')
              .order_by('-created_at')[:400]):
        terms, grams = _read(f'{c.title} {c.body}')
        shared = asked & terms
        same = bool(door & grams)
        if same or (len(shared) >= 2 and len(shared) / len(asked) >= 0.75):
            found.append((c, same, len(shared) / len(asked) if asked else 0))
    found.sort(key=lambda x: (-x[1], -x[2], -x[0].useful_count))
    found = found[:limit]
    answers = {a.parent_id: a for a in Contribution.objects.filter(counters.published(),
                                                                   pk__in=[c.answer_id for c, _, _ in found if c.answer_id])
               .only('id', 'parent_id', 'body', 'accepted_at', 'useful_count')}
    out = []
    for c, _, _ in found:
        best = answers.get(c.pk)
        best = best if best is not None and best.body else None
        out.append({'id': c.pk, 'title': c.title, 'body': c.body[:200], 'path': f'{path}/{c.pk}',
                    'created_at': c.created_at, 'answers': c.reply_count, 'useful': c.useful_count,
                    'answer': best and {'body': best.body[:240], 'accepted': best.accepted_at is not None,
                                        'useful': best.useful_count}})
    return out
