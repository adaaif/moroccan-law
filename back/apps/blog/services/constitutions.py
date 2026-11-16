"""The six constitutions counted side by side, for «ستة دساتير في صفحة واحدة» (the blog's second post, B7 of
the blog-first-post review, 31 Oct 2026): each as first issued (its earliest Arabic version: Adala's copy of the text as published),
its titles («أبواب») with their articles and words, each article with what became of it since the constitution before
(the corpus's lineage: the same words, rewritten, or no article before it), a few words counted in each, and the dates
from the referendum to the Bulletin (data/constitutions.json). Three queries whatever the constitutions.

Words are the spaces in an article plus one, as in the first post. A title is matched to a theme by the patterns in
the post's meta, so «البرلمان», «مجلس النواب» and «السلطة التشريعية» line up across the six."""
import re
from collections import Counter

from apps.corpus.models import Article, Text, TextType, Version
from apps.corpus.services import constitutions
from apps.corpus.services.addresses import text_path

# What became of an article since the constitution before it, as the lineage says (0: the first constitution).
STATES = {'same': 1, 'changed': 2, 'unsure': 3, 'none': 4}
LETTERS = re.compile(r'[ء-ي]+')
MARKS = re.compile(r'[ً-ْـ]')


def fold(word: str) -> str:
    """A word as the counts compare it: no short vowels or stretching, every alef plain, «ى» as «ي», «ة» as «ه»."""
    word = MARKS.sub('', word)
    return word.translate(str.maketrans('أإآى', 'اااي')).replace('ة', 'ه')


def bare(token: str) -> str:
    """A word without the «و» or «ف» before it, and with «بال», «لل», «كال» read as «ال»: «وللملك» counts as «الملك»."""
    token = fold(token)
    if len(token) > 3 and token[0] in 'وف':
        token = token[1:]
    for lead, to in (('بال', 'ال'), ('كال', 'ال'), ('لل', 'ال')):
        if token.startswith(lead) and len(token) > len(lead) + 1:
            return to + token[len(lead):]
    return token


def words(body: str) -> int:
    return body.count(' ') + 1


def count(meta: dict) -> dict:
    themes = [(t['key'], re.compile(t['match'])) for t in meta['themes'] if t.get('match')]
    terms = {t['key']: {fold(f) for f in t['forms']} for t in meta['terms']}
    texts = list(Text.objects.filter(type=TextType.CONSTITUTION).order_by('signed_on'))
    first: dict[int, Version] = {}
    for v in Version.objects.filter(text__in=texts, language='ar').order_by('text_id', 'valid_from', 'pk'):
        first.setdefault(v.text_id, v)
    by_version: dict[int, list[dict]] = {v.pk: [] for v in first.values()}
    for a in (Article.objects.filter(version__in=first.values())
              .values('version_id', 'order', 'number', 'eid', 'heading_path', 'body').order_by('version_id', 'order')):
        by_version[a['version_id']].append(a)
    lineage = constitutions._lineage()['pairs']
    facts = constitutions.by_uri()

    out = []
    for text in texts:
        f = facts.get(text.akn_uri)
        if f is None or text.pk not in first:
            continue
        links = lineage.get(str(f['year']), {}).get('links', {})
        arts = by_version[first[text.pk].pk]
        titles: list[dict] = []
        squares, tally, preamble = [], Counter(), 0
        for a in arts:
            if a['number'] == 'preamble':
                preamble = words(a['body'])
            else:
                name = (a['heading_path'] or [''])[0]
                if not titles or titles[-1]['name'] != name:
                    theme = next((k for k, p in themes if p.search(name)), '')
                    titles.append({'name': name, 'theme': theme, 'articles': 0, 'words': 0})
                titles[-1]['articles'] += 1
                titles[-1]['words'] += words(a['body'])
                link = links.get(a['eid'])
                squares.append([a['number'], len(titles) - 1, STATES.get(link[1], 3) if link else (4 if links else 0)])
            tally.update(t for t in (bare(w) for w in LETTERS.findall(a['body'])))
        # The articles kept word for word, quoted when they are few (2011 kept four of 1996's).
        kept = [[a['number'], a['body']] for a, q in zip((a for a in arts if a['number'] != 'preamble'), squares) if q[2] == 1]
        out.append({
            'year': f['year'], 'path': text_path(text.akn_uri), 'referendum': f['referendum'], 'signed': f['signed'],
            'published': f['published'], 'issue': f['issue'], 'page': f['page'],
            'articles': len(squares), 'words': sum(t['words'] for t in titles), 'preamble': preamble,
            'titles': titles, 'squares': squares,
            'terms': {k: sum(tally[w] for w in forms) for k, forms in terms.items()},
            'quotes': kept if len(kept) <= 10 else [],
        })
    return {'constitutions': out, 'square_fields': ['number', 'title', 'state'], 'states': STATES}
