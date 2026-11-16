"""What a reader needs around an article's words, marked where they stand (char offsets in the body):

- `link`: a citation the article makes, pointing at the article or text it names when the corpus holds it
  («المادة 5 أعلاه» → this text's article 5; «القانون رقم 31.13» → that law), or saying it does not;
- `term`: a word this text defines in its own definitions article («يقصد في مدلول هذا القانون بـ: …»),
  marked once an article, the definition shown on tap;
- `word`: a word that opens the law (R9 of the for-everyone review: «النفقة», «الوجيبة الكرائية»), marked once an article
  and only once its meaning was written and checked (HM35 of the hard-moment review: 58 words were dotted and
  none had one), the meaning by register in the mark (`means`), opened in place like a defined term.

Computed from the words on each request; ma_law (Rust) reads them.
"""
import re
from datetime import date

import ma_law

from apps.corpus.models import Article, Mention, Text
from apps.corpus.services import constitutions
from apps.corpus.services.addresses import article_path, text_path
from apps.corpus.services.citations import resolve_many
from apps.corpus.services.codes import dated
from apps.explain.services import concepts, explanations

# An article that defines this text's words says so.
DEFINES = re.compile(r'يقصد ب|يراد ب|المصطلحات التالية|العبارات التالية|في مدلول هذ|on entend par|au sens d', re.I)
# One definition a line: «- الإدارة : …», «2. المقاولة: …», «أ) المشغل : …», «"الوثيقة" : …».
TERM_LINE = re.compile(
    r'^\s*(?:[-–•*]|\d{1,2}\s*[.\-)]|[ء-ي]\s*[.\-)])?\s*(?:يقصد ب|يراد ب)?\s*[«"“]?'
    r'(?P<term>[^:«»"“”\d\n]{2,60}?)[»"”]?\s*[:：]\s*(?P<definition>.{8,})$')
MAX_TERM_WORDS = 6
# An article that changes another text: its bare «المادة 7» names the other text's article, not this one's.
AMENDS = re.compile(r'تغير|يغير|تتمم|يتمم|تنسخ|ينسخ|تعوض|يعوض|تحذف|يحذف|كما يلي|على النحو التالي|modifi|complét|abrog')


# «يقصد في مدلول هذا المرسوم ب «الدواء» كل دواء …»: one term defined in the sentence itself.
INLINE = re.compile(r'(?:يقصد|يراد)\s+(?:في مدلول هذ\S*\s+)?(?:ب|بـ)\s*«(?P<term>[^»\n]{2,60})»\s*:?\s*'
                    r'(?P<definition>[^؛\n]{8,})')


def definitions(articles: list[Article]) -> list[dict]:
    """[{term, eid, definition}] from the articles that define this text's words, in their order. An article
    that changes another text is passed over: the definitions it quotes are that text's."""
    out, seen = [], set()

    def add(term: str, definition: str, eid: str):
        term = term.replace('**', '').strip(' -–،,')
        folded = ma_law.fold(term)
        if folded and len(folded.split()) <= MAX_TERM_WORDS and folded not in seen:
            seen.add(folded)
            out.append({'term': term, 'eid': eid, 'definition': definition.replace('**', '').strip()[:500]})

    for a in articles:
        if not DEFINES.search(a.body) or AMENDS.search(a.body):
            continue
        for m in INLINE.finditer(a.body):
            add(m['term'], m['definition'], a.eid)
        for line in a.body.splitlines():
            m = TERM_LINE.match(line)
            if m:
                add(m['term'], m['definition'], a.eid)
    return out


def _key(c: dict) -> tuple:
    """What a citation's link depends on: its words' place aside."""
    return tuple(c.get(k) for k in ('kind', 'article', 'text_kind', 'text_number', 'code', 'issue', 'issue_suffix'))


def _mirror(number: str) -> str:
    """«1-595» for «595-1»: an article added to a code is numbered after the one it follows, and the links pipeline
    kept some the other way round."""
    parts = number.split('-')
    return '-'.join(reversed(parts)) if len(parts) == 2 and all(p.isdigit() for p in parts) else number


def _eids(wanted: set[tuple[str, str]]) -> dict[tuple[str, str], str]:
    """{(text, article number as a link kept it): the article's address} for the articles those texts hold, the number as
    kept or mirrored (RD17 of the readers review, 9 Nov 2026: 72 of the 2,758 article links a crawler followed led
    nowhere). One query, and none when no link leads to another text."""
    if not wanted:
        return {}
    numbers = {n for _, n in wanted} | {_mirror(n) for _, n in wanted}
    there = {(uri, number): eid for uri, number, eid in Article.objects.filter(
        version__text__akn_uri__in={u for u, _ in wanted}, number__in=numbers, version__language='ar')
        .order_by('version__valid_from').values_list('version__text__akn_uri', 'number', 'eid')}
    return {(uri, n): there.get((uri, n)) or there[(uri, _mirror(n))] for uri, n in wanted
            if (uri, n) in there or (uri, _mirror(n)) in there}


def _overlaps(marks: list[dict], start: int, end: int) -> bool:
    return any(start < m['end'] and m['start'] < end for m in marks)


def marks(text: Text, articles: list[Article], defined: list[dict], among: list[Article] | None = None) -> dict[str, list[dict]]:
    """{eid: [mark…]} sorted by start, never overlapping (a link wins over a term). `among`: all the text's
    articles, when `articles` is only some of them, so «المادة 12» still finds article 12."""
    by_number = {a.number: a for a in (among or articles) if a.number}
    published = text.first_published_in.date if text.first_published_in_id else text.signed_on
    if c := constitutions.by_uri().get(text.akn_uri):
        # Signed days before its BO: dated by its dahir, a constitution's «الدستور» was the one it replaced.
        published = date.fromisoformat(c['published'])
    # Every citation of the window first: the other texts it names are resolved together (S3 of the performance audit).
    cited = {a.eid: [dated(a.body, c) for c in ma_law.parse_citations(a.body)] for a in articles}
    other = {}
    for c in (c for found in cited.values() for c in found):
        if not (c['kind'] == 'article' and not (c['code'] or c['text_number'])):
            other.setdefault(_key(c), c)
    resolved = dict(zip(other, resolve_many(list(other.values()), on=published)))
    # In an amending article a bare «المادة 7» is the amended text's: the links pipeline kept where it leads.
    elsewhere = {(m.from_eid, m.start): m for m in Mention.objects.filter(
        from_uri=text.akn_uri, from_eid__in=[a.eid for a in articles], kind=Mention.Kind.CITES,
        state=Mention.State.RESOLVED).exclude(to_uri=text.akn_uri) if m.to_number}
    held = set(Text.objects.filter(akn_uri__in={m.to_uri for m in elsewhere.values()}, versions__isnull=False)
               .values_list('akn_uri', flat=True))
    there_eids = _eids({(m.to_uri, m.to_number) for m in elsewhere.values() if m.to_uri in held})
    # A term is looked for in an article only when its folded words are in the article's: find_folded folds the
    # whole article for each term (1,924 calls, 0.32 s on the finance law), and fold() is the text it searches.
    terms = [ma_law.fold(d['term']) for d in defined]
    meanings = explanations.word_meanings()
    words = [(c, ma_law.fold(c['search'])) for c in concepts.load() if c['slug'] in meanings]
    out: dict[str, list[dict]] = {}
    for a in articles:
        found: list[dict] = []
        amends = bool(AMENDS.search(a.body))
        folded = ma_law.fold(a.body)
        for c in cited[a.eid]:
            if _overlaps(found, c['start'], c['end']):
                continue
            mark = {'start': c['start'], 'end': c['end'], 'kind': 'link'}
            if c['kind'] == 'article' and not (c['code'] or c['text_number']):
                there = elsewhere.get((a.eid, c['start'])) if amends else None
                if there is not None:
                    held_there = there.to_uri in held
                    # The article's own address when the text holds it, else the text's: never an address written from
                    # the number, which led nowhere for «الفصل 595-1» (kept as «1-595») and for every article not held.
                    eid = there_eids.get((there.to_uri, there.to_number))
                    mark.update(href=(article_path(there.to_uri, eid) if eid else text_path(there.to_uri)) if held_there else None,
                                state='found' if held_there else 'not_in_corpus', title=there.words)
                else:
                    target = None if amends else by_number.get(c['article'])
                    if target is None or target.eid == a.eid:
                        continue
                    mark.update(href=article_path(text.akn_uri, target.eid), state='found', title=target.label)
            else:
                r = resolved[_key(c)]
                href = None
                if r['state'] in ('found', 'text_only', 'repealed'):
                    href = r['article']['path'] if r['article'] else r['text']['path']
                elif r['state'] == 'issue':
                    href = r['issue']['path']
                title = r['text']['title'] if r['text'] else (r['name'] or {}).get('ar')
                mark.update(href=href, state=r['state'], title=(title or '')[:200])
            found.append(mark)
        for i, d in enumerate(defined):
            if d['eid'] == a.eid or not terms[i] or terms[i] not in folded:
                continue
            for start, end in ma_law.find_folded(a.body, d['term'])[:1]:
                if not _overlaps(found, start, end):
                    found.append({'start': start, 'end': end, 'kind': 'term', 'term': i})
        for c, word in words:
            if not word or word not in folded:
                continue
            for start, end in ma_law.find_folded(a.body, c['search'])[:1]:
                if not _overlaps(found, start, end):
                    found.append({'start': start, 'end': end, 'kind': 'word', 'slug': c['slug'],
                                  'means': meanings[c['slug']]})
        out[a.eid] = sorted(found, key=lambda m: m['start'])
    return out
