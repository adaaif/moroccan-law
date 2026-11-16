"""Life topics (R2 of the for-everyone review, 19 Oct 2026): «الأسرة», «الشغل», «السكن والكراء»… — how people name the part
of life a law governs. data/topics.json says what each holds: codes of the shelf, situations, the words that open
its laws, and the words a new text's title must hold to count among its recent changes."""
import json
from datetime import timedelta
from functools import lru_cache, reduce
from operator import or_
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.corpus.models import Text
from apps.sources.models import Issue
from apps.corpus.services.addresses import text_path
from apps.corpus.services.codes import books
from apps.corpus.services.situations import published

DATA = Path(__file__).resolve().parent.parent / 'data' / 'topics.json'
# A recent change is a rule-making text of the general section, from the last half year.
RECENT_DAYS = 183
RECENT_TYPES = ('law', 'organic_law', 'decree_law', 'decree', 'order', 'dahir')
RECENT_MOST = 6


def load() -> list[dict]:
    return json.loads(DATA.read_text())['topics']


def find(slug: str) -> dict | None:
    return next((t for t in load() if t['slug'] == slug), None)


def summary(topic: dict) -> dict:
    # `short`: the door's name under its arch on the home (U3 of the Moroccan-design review).
    return {'slug': topic['slug'], 'name': topic['name'], 'short': topic.get('short') or topic['name'], 'lead': topic['lead'],
            'counts': {'situations': len(topic['situations']), 'codes': len(topic['codes'])}}


def recent(topic: dict, today=None) -> list[dict]:
    """The topic's rule-making texts of the last half year, newest first: those that change one of its texts (the links
    pipeline's changes) and those whose title holds one of its words, outside the names that only borrow a word (M7 of
    the land review: «التعمير» in the World Bank's Arabic name brought its loans to the land topic)."""
    if not topic['keywords']:
        return []
    from apps.consolidation.models import Change
    from apps.corpus.services.codes import texts_of

    since = (today or timezone.localdate()) - timedelta(days=RECENT_DAYS)
    # The half year's issues first, then their texts' titles: asked together, Postgres read all 32,000 titles with
    # every keyword before joining the issue (S9 of the performance audit: 163 ms, up to 740 ms busy).
    issues = list(Issue.objects.filter(edition='general_ar', date__gte=since).values_list('pk', flat=True))
    own = [t.akn_uri for t in texts_of(topic['codes']).values() if t is not None]
    changers = Change.objects.filter(text_uri__in=own).values('by_uri') if own else None
    match = reduce(or_, (Q(title_ar__icontains=w) for w in topic['keywords']))
    if changers is not None:
        match |= Q(akn_uri__in=changers)
    texts = (Text.objects.filter(match, type__in=RECENT_TYPES, first_published_in_id__in=issues)
             .exclude(bo_section='special').select_related('first_published_in')
             .order_by('-first_published_in__date', '-id')[:RECENT_MOST * 3])
    from apps.corpus.services.codes import display_name
    # The texts among them that change one of the topic's, in one query (never one a text).
    changing = set(Change.objects.filter(by_uri__in=[t.akn_uri for t in texts], text_uri__in=own)
                   .values_list('by_uri', flat=True)) if own and texts else set()
    kept = [t for t in texts if t.akn_uri in changing or _says(t.title_ar, topic['keywords'])][:RECENT_MOST]
    return [{'path': text_path(t.akn_uri), 'title': t.title_ar, 'name': display_name(t), 'type': t.type, 'number_as_printed': t.number_as_printed,
             'date': t.first_published_in.date, 'issue': t.first_published_in.key, 'status': t.status} for t in kept]


# Names that hold a topic's word without being about it: the word inside them does not count (the World Bank's loans;
# a minister's title, whose orders on contractors' categories or a ministry's staff are not the land's law).
BORROWED = ('البنك الدولي للإنشاء والتعمير', 'إعداد التراب الوطني والتعمير',
            # The health minister's title (the health review, S5): it put signature delegations in the topic's
            # news; an order the minister signs still shows when its subject holds a health word.
            'وزير الصحة والحماية الاجتماعية', 'وزيرة الصحة والحماية الاجتماعية', 'وزارة الصحة والحماية الاجتماعية',
            'وزير الصحة', 'وزيرة الصحة', 'وزارة الصحة')


def _says(title: str, words: list[str]) -> bool:
    """A title holds one of the words outside the names that only borrow them."""
    for name in BORROWED:
        title = title.replace(name, '')
    return any(w in title for w in words)


def of_title(title: str) -> dict | None:
    """The first topic one of whose words a title holds: how a new text joins a topic (as in `recent`)."""
    return next(({'slug': t['slug'], 'name': t['name']} for t in load() if _says(title, t['keywords'])), None)


def detail(topic: dict, talk: bool = True) -> dict:
    """A topic's page: its situations as readers see them, its codes as the shelf has them, its recent changes; and
    unless `talk` is False, its conversation (kept apart: it changes with every contribution, the rest with the law)."""
    listed = {b['key']: b for b in books(topic['codes'])}
    # While developing, the situations' drafts too, as the situations' page shows them.
    shown = {s['slug']: s for s in published(include_drafts=settings.SHOW_DRAFTS, only=topic['situations'])}
    from apps.explain.services import concepts

    codes = [listed[k] for k in topic['codes'] if k in listed]
    # Its words by their terms, for the chips that open them (P16 of the polish review).
    words = [{'slug': c['slug'], 'term': c['term']} for c in (concepts.find(w) for w in topic['words']) if c and not c['built_in']]
    out = {**summary(topic), 'words': words,
           'situations': [shown[s] for s in topic['situations'] if s in shown],
           'codes': codes}
    if talk:
        out['talk'] = talk_of(topic['slug'])
    return {**out, 'recent': recent(topic)}


def talk_of(slug: str) -> dict:
    """A topic's conversation: its place's liveliest posts, its questions waiting, its moderators."""
    from apps.discussion.services.thread import topic_talk

    return topic_talk(slug)


def _variants(word: str) -> set[str]:
    """A typed word and the word inside it: «فالكرا» holds «الكرا», «وطلقني» holds «طلقني»."""
    out = {word}
    for prefix in ('ف', 'و', 'ب', 'ل', 'وال', 'فال', 'بال'):
        if word.startswith(prefix) and len(word) > len(prefix) + 2:
            rest = word[len(prefix):]
            out.add(rest if not prefix.endswith('ال') else 'ال' + rest)
    return out


def question_grams(query: str) -> set[str]:
    """A question's words folded, alone and in runs of two and three, each first word with the word inside it; and the
    same runs with each Darija verb brought to one form (darija.core: «شداتو البوليس» also as «شد البوليس»), which a
    door's words meet through `names`."""
    from apps.sources.services.compare import fold
    from apps.topics.services.darija import core

    tokens = fold(query).split()
    cores = [core(t) for t in tokens]
    grams = set()
    # Runs as long as the longest door or topic word (HM1 of the hard-moment review: runs of three never met the
    # 365 door words of four or more, «لا ترد ولا تستبدل», «شريت حاجة وطلعات خاسرة»).
    for n in range(1, longest_word() + 1):
        for i in range(len(tokens) - n + 1):
            for first in _variants(tokens[i]):
                grams.add(' '.join([first, *tokens[i + 1:i + n]]))
                grams.add(CORED + ' '.join([core(first), *cores[i + 1:i + n]]))
    return grams


# A cored run is marked apart in the grams: a door's verb meets the question's verbs, never its words as typed («كنتمشى»
# cored is «تمشي», which a question's «تمشي», cored «مش», is not).
CORED = '\x00'


@lru_cache(maxsize=1)
def longest_word() -> int:
    """The most words in a door's, a tool's or a topic's word, at most eight: how long a question's runs must be."""
    from apps.topics.services import kit

    words = [w for t in load() for w in [*t.get('everyday', []), *t['keywords']]]
    for slug in kit._folders():
        hub = kit.load(slug)['hub']
        words += [w for d in [*(hub.get('events') or []), *(hub.get('tools') or [])] for w in d.get('words') or []]
    return min(8, max((len(folded(w).split()) for w in words), default=3))


def names(word: str, grams: set[str]) -> bool:
    """Whether a question (its `question_grams`) names a topic's or door's word, as written or in another person
    («شدوه البوليس» in «شداتو البوليس», «بغيت نطلق» in «راجلي بغا يطلقني»)."""
    from apps.topics.services.darija import door_key

    w = folded(word)
    return w in grams or CORED + (door_key(w) or w) in grams


@lru_cache(maxsize=8192)
def folded(word: str) -> str:
    """A topic's or a door's word folded once for the process: matching a question used to fold every topic word again
    on every keystroke (1,184 folds, 62 ms of a suggestion)."""
    from apps.sources.services.compare import fold

    return fold(word)


def named(query: str) -> dict[str, list[str]]:
    """The topics a question names, each with its own words the question says (folded): {slug: [words]}. What `matching`
    counts; the doors read it to tell the topic a question is about from a door that only shares a word with it
    (kit.matching)."""
    grams = question_grams(query)
    out = {}
    for topic in load():
        said = [folded(w) for w in topic.get('everyday', []) + topic['keywords'] if names(w, grams)]
        if said:
            out[topic['slug']] = said
    return out


def matching(query: str, most: int = 2) -> list[dict]:
    """The topics a question names in the words people use («مول الدار بغا يخرجني» → السكن والكراء), most words
    first. Only a hint above the results: it never changes what search finds."""
    grams = question_grams(query)
    scored = []
    for topic in load():
        hits = sum(1 for w in topic.get('everyday', []) + topic['keywords'] if names(w, grams))
        if hits:
            scored.append((hits, topic))
    scored.sort(key=lambda x: -x[0])
    return [{'slug': t['slug'], 'name': t['name']} for _, t in scored[:most]]
