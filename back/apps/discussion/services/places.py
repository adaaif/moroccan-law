"""Where people write (29 Oct 2026): a topic's place, /talk/<slug>, one for each of the twelve life topics
and «general» for a law no topic holds. A post lives in a place; the law stays one tap away through what it cites.

A post's own address is /talk/<slug>/<id>: its followers, its notices and its letters hang on it, so a busy topic is
one letter a post, not one a topic."""
from dataclasses import dataclass

from apps.accounts.services.refusals import Refused

PREFIX = '/talk/'
GENERAL = 'general'
GENERAL_NAME = {'ar': 'أسئلة أخرى', 'fr': 'Autres questions'}


@dataclass(frozen=True)
class Place:
    slug: str
    name: dict
    # The name a door carries, as on the home's doors («الطريق والسياقة» → «الطريق»).
    short: dict | None = None

    @property
    def path(self) -> str:
        return f'{PREFIX}{self.slug}'


def all_places() -> list[Place]:
    """The twelve topics in their order, then the general place."""
    from apps.topics.services import topics

    return [Place(t['slug'], t['name'], t.get('short') or t['name']) for t in topics.load()] + [
        Place(GENERAL, GENERAL_NAME, GENERAL_NAME)]


def find(path: str) -> Place:
    slug = str(path or '').removeprefix(PREFIX).strip('/') if str(path or '').startswith(PREFIX) else ''
    found = next((p for p in all_places() if p.slug == slug), None)
    if found is None:
        raise Refused('path', 'not_found', 404)
    return found


def is_place(path: str) -> bool:
    return str(path or '').startswith(PREFIX) and str(path).count('/') == 2


def post_path(c) -> str:
    """A post's own address, from the post or a comment under it."""
    top = c.parent or c
    return f'{c.discussion.path}/{top.pk}'


def notice_path(c) -> str:
    """Where a notice about a contribution points: its post in a topic, or an article thread as before."""
    return post_path(c) if is_place(c.discussion.path) else c.discussion.path


def split_post(path: str) -> tuple[str, int | None]:
    """'/talk/family/12' → ('/talk/family', 12); a place alone → (place, None)."""
    head, _, tail = str(path or '').rpartition('/')
    # `isdecimal()`: «²» is a digit to `isdigit()` and no number to `int()`; a post's number has ten digits at most.
    if head.startswith(PREFIX) and tail.isdecimal() and len(tail) <= 10:
        return head, int(tail)
    return str(path or ''), None


def of_texts() -> dict[str, list[str]]:
    """Each text's address and the places of the topics that hold it, in the topics' order, kept with the corpus."""
    from apps.corpus.services import generation
    from apps.topics.services import topics as topic_data

    def made():
        from apps.corpus.services.addresses import text_path
        from apps.corpus.services.codes import texts_of
        from apps.topics.services import topics

        listed = topics.load()
        found = texts_of(sorted({k for t in listed for k in t['codes']}))
        out: dict[str, list[str]] = {}
        for t in listed:
            for key in t['codes']:
                text = found.get(key)
                if text is not None and t['slug'] not in out.setdefault(text_path(text.akn_uri), []):
                    out[text_path(text.akn_uri)].append(t['slug'])
        return out
    return generation.kept(['places-of-texts', generation.files(topic_data.DATA)], made)


def of_text(text_path: str) -> list[Place]:
    """Where a question on this text's articles may go: its topics' places, else the general place."""
    by_slug = {p.slug: p for p in all_places()}
    return [by_slug[s] for s in of_texts().get(text_path, []) if s in by_slug] or [by_slug[GENERAL]]


def label(path: str, viewer_id: int | None = None) -> dict:
    """A place's name, or a post's: the place and the post's title, for notices, letters and lists. The title only
    while readers may read the post, or for its author (`viewer_id`)."""
    from django.db.models import Q

    from apps.discussion.models import Contribution
    from apps.discussion.services import counters

    place_path, pk = split_post(path)
    try:
        place = find(place_path)
    except Refused:
        return {'place': '', 'name': None, 'title': ''}
    title = ''
    if pk:
        shown = counters.published() | Q(author_id=viewer_id) if viewer_id else counters.published()
        title = Contribution.objects.filter(shown, pk=pk).values_list('title', flat=True).first() or ''
    return {'place': place.slug, 'name': place.name, 'title': title}
