"""The doors and tools a question names in people's words (`matching`), the doors nearest a question none names
(`nearest`), a door's own words, the articles the item a door leads to cites, and a search's private words (violence,
F14 of the family plan), kept as a count only."""
from apps.topics.services.kit.folders import KINDS, _folders, load
from apps.topics.services.kit.items import articles, cited, cited_in_order, shown
from apps.topics.services.kit.topic_page import door_path, reachable


def matching(query: str) -> list[dict]:
    """The doors and tools a question names in people's words («كيفاش نقسمو الورث» → the inheritance calculator), as
    search suggests guides: {slug, title, path}. Only what may be shown."""
    from apps.topics.services.topics import folded as fold, names, question_grams

    grams = question_grams(query)
    asks = _asks(grams)
    plain = fold(query)
    out = []
    for slug in _folders():
        h = load(slug)['hub']
        # What a door may lead to: the folder's items shown, and the hub's tools shown (a door may open a tool).
        open_ = ({f'{k}/{key}' for k in KINDS for key, i in load(slug)[k].items() if shown(i)}
                 | {f'tools/{t["key"]}' for t in h.get('tools') or [] if shown(t)})
        for d in [*(h.get('tools') or []), *(h.get('events') or [])]:
            said = [fold(w) for w in d.get('words') or [] if names(w, grams)]
            exact = sum(1 for w in said if w in grams)
            if not said:
                continue
            if d.get('to') and not reachable(d['to'], open_):
                continue
            if not d.get('to') and not shown(d):
                continue
            topic, own, path = door_path(slug, d)
            # Where the question says the door's words: the one it says first is what it is about.
            at = min((plain.find(w) for w in said if w in plain), default=len(plain))
            out.append({'slug': f'{slug}-{d["key"]}', 'title': d['title'], 'path': path, 'lead': d.get('lead'),
                        'icon': d.get('icon'), 'topic': topic, 'ref': own, 'mark': d.get('mark'),
                        '_words': max(len(w.split()) for w in said), '_said': len(said), '_exact': exact,
                        '_fits': _fits(asks, d.get('mark')), '_at': at, '_phrases': said, '_home': slug})
    # The topic whose door says most of the question first (E16 of the work-counted review): the work's «كونجي الولادة» before
    # the family's «الولادة», «ما صرحش بيا» before «الضمان» (a consumer's warranty); within a topic, the door that says
    # most of it («démarchage à domicile» before «rétractation», the consumer-receipt review); else the folder's order.
    best: dict[str, tuple] = {}
    for d in out:
        best[d['topic']] = min(best.get(d['topic'], (0, 0)), (-d['_words'], -d['_said']))
    from apps.topics.services import topics as every
    named = every.named(query)
    # A door that claims the question only by another topic's own word is a guess (RD8 of the readers review,
    # 10 Nov 2026: 17 of 145 questions were answered by a door of another topic, in the site's surest voice). «مول الدار
    # ما بغاش يرجع ليا الكوسيون» opened public procurement's guarantee: «الكوسيون» is that door's word, and the housing
    # topic's, which the question names by «مول الدار» too; «augmentation loyer maximum» opened the landlord's income
    # tax by «loyer». Such a door is `unsure`: the page offers it under «واش بغيتي تقول», never as the answer. A word no
    # named topic owns stands («sextorsion» with «plainte»): the topics' own lists are short, and a first rule that kept
    # only the doors of the topics a question names lost 25 of the gold sets' answers to win these.
    for d in out:
        # Another topic owns the door's words, and the question names that topic by a word more than them: «congé»
        # alone, the housing's word for a notice, takes nothing from the work's «congé annuel».
        said = set(d['_phrases'])
        if d['topic'] not in named and d['_home'] not in named and any(
                said <= set(words) and set(words) - said for slug, words in named.items()):
            d['unsure'] = True
    # A tie between topics goes to the topic the rest of the question names (its everyday words and keywords), never to
    # the slug that sorts first (HM10 of the hard-moment review: the family's dates before the housing's eviction).
    rank = {slug: i for i, slug in enumerate(sorted(named, key=lambda t: -len(named[t])))}
    # Within a topic: the door that says most of the question, then the one whose words come first in it («سقوط الحضانة
    # بزواج الأم» is about custody), then the one the reader's own word names over one met only through another
    # person's form («الخدامة فالدار طردتها»: the domestic worker before the Labour Code's dismissal).
    out.sort(key=lambda d: (best[d['topic']], rank.get(d['topic'], len(rank)), d['topic'], -d['_words'],
                            -d['_exact'], -d['_fits'], -d['_said'], d['_at']))
    return [{k: v for k, v in d.items() if not k.startswith('_')} for d in out]




# Words that ask or join, never what a question is about: no door is near a question by them.
_PLAIN = set("""واش كيفاش كيف شنو اش علاش فين اين منين شحال قداش كم امتي متي فوقاش هل ماذا لماذا ما ماهي هي هو هاد هادي
هذا هذه ديال ديالي باش خاصني خصني خاص خص خاصو خاصها بغيت بغا بغات نعرف عافاك ممكن يمكن نقدر يقدر عندي عندو من في على علي لي مع عند الى الي
او ولا ولكن بلا حتي غير شي واحد وحده دابا بزاف كاين كاينه راه انا هوما حنا نتوما والو كل ان اللي التي الذي غادي غاديه
ديالو ديالها ديالنا ديالكم ديالهم""".split())


def nearest(query: str, topic: str | None = None, most: int = 3) -> list[dict]:
    """The doors nearest a question no door names (HM8 of the hard-moment review, 7 Nov 2026): «واش بغيتي تقول…»
    instead of a 1928 dahir. Each shown door is scored by the content words it shares with the question (its words and
    title, Darija verbs brought to one form), a word fewer doors hold counting more; the doors of the topic the question
    names first, else every topic's. Only what may be shown, as `matching`."""
    import math

    from apps.sources.services.compare import fold
    from apps.topics.services.darija import core

    from apps.topics.services.topics import _variants

    def content(text: str) -> set[str]:
        words = {core(v) for t in fold(text).split() for v in _variants(t)}
        return {c for c in words if len(c) >= 3 and c not in _PLAIN and not c.isdigit()}

    asked = content(query)
    if not asked:
        return []
    doors = []
    for slug in _folders():
        h = load(slug)['hub']
        open_ = ({f'{k}/{key}' for k in KINDS for key, i in load(slug)[k].items() if shown(i)}
                 | {f'tools/{t["key"]}' for t in h.get('tools') or [] if shown(t)})
        for d in h.get('events') or []:
            if (d.get('to') and not reachable(d['to'], open_)) or (not d.get('to') and not shown(d)):
                continue
            words = content(' '.join([*(d.get('words') or []), (d.get('title') or {}).get('ar', '')]))
            doors.append((slug, d, words))
    df: dict[str, int] = {}
    for _, _, words in doors:
        for w in words:
            df[w] = df.get(w, 0) + 1
    scored = []
    for slug, d, words in doors:
        shared = asked & words
        # Within the topic the question names, one word it shares is enough; anywhere else, two.
        if shared and (slug == topic or len(shared) >= 2):
            scored.append((sum(math.log(len(doors) / df[w]) for w in shared), slug, d))
    scored.sort(key=lambda x: (x[1] != topic, -x[0]))
    out = []
    for _, slug, d in scored[:most]:
        t, own, path = door_path(slug, d)
        out.append({'slug': f'{slug}-{d["key"]}', 'title': d['title'], 'path': path, 'lead': d.get('lead'),
                    'icon': d.get('icon'), 'topic': t, 'ref': own})
    return out


# A question that asks how much or how long (HM9 of the hard-moment review): between two doors that say as much of
# it, the one whose figure is money for «شحال/قداش/combien», a span of time for «فوقاش/délai».
_HOW_MUCH = {'شحال', 'قداش', 'كم', 'combien', 'montant', 'chhal', 'ch7al'}
_WHEN = {'فوقاش', 'امتي', 'متي', 'اجل', 'délai', 'delai', 'quand', 'fo9ach', 'fou9ach'}
_MONEY = ('درهم', 'dh', 'mad', 'dirham')
_TIME = ('يوم', 'ساعه', 'ساعة', 'شهر', 'شهور', 'أسبوع', 'اسبوع', 'عام', 'سنه', 'jour', 'heure', 'mois', 'semaine', 'an')


def _asks(grams: set[str]) -> str:
    words = {g for g in grams if ' ' not in g}
    return 'money' if words & _HOW_MUCH else 'time' if words & _WHEN else ''


def _fits(asks: str, mark: dict | None) -> int:
    if not asks or not mark:
        return 0
    unit = ' '.join(str(v) for v in (mark.get('unit') or {}).values()).lower() if isinstance(mark.get('unit'), dict) else str(mark.get('unit') or '')
    return int(any(u in unit for u in (_MONEY if asks == 'money' else _TIME)))


def door_words(door: str) -> list[str]:
    """The words of a door or tool `matching` named (its slug, «housing-increase»): what a question that names it says."""
    for slug in _folders():
        h = load(slug)['hub']
        for d in [*(h.get('tools') or []), *(h.get('events') or [])]:
            if f'{slug}-{d["key"]}' == door:
                return list(d.get('words') or [])
    return []


def door_articles(topic: str, ref: str, most: int = 3) -> list[dict]:
    """The first articles the item a door leads to cites, for search to answer with right under the door (U17 of
    the Moroccan-design review): the law the door's answer rests on, before the texts the words found. Two queries."""
    item = _item(topic, ref)
    paths = cited_in_order(item)[:most] if item else []
    found = articles(set(paths)) if paths else {}
    return [{k: found[p][k] for k in ('path', 'label', 'number', 'text', 'body')} for p in paths if p in found]


def door_cites(topic: str, ref: str) -> set[str]:
    """The articles the item a door leads to cites (X3 of the road tools review): a question answered by a door whose
    journey or page cites the expected article is answered, and the goldset says it was by the door."""
    item = _item(topic, ref)
    return cited(item) if item else set()


def _item(topic: str, ref: str) -> dict | None:
    """The item a door leads to: a journey, page… of the folder, or a tool of the hub with the articles it rests on (its
    `cites`, the tax review: the salary tool rests on arts 59, 73 and 74)."""
    content = load(topic) or {}
    kind, _, key = ref.partition('/')
    if kind == 'tools':
        return next((t for t in content.get('hub', {}).get('tools') or [] if t.get('key') == key), None)
    return (content.get(kind) or {}).get(key)


def private(query: str) -> bool:
    """A search that holds one of a topic's private words (violence, F14 of the family plan): kept as a count only,
    never as typed, and never among the device's last searches."""
    from apps.sources.services.compare import fold
    from apps.topics.services.topics import question_grams

    grams = question_grams(query)
    return any(fold(w) in grams for slug in _folders() for w in load(slug)['hub'].get('private') or [])
