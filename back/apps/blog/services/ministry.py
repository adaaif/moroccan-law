"""The education portfolio's names, for «وزارة واحدة، وأسماء كثيرة» (the blog's twenty-sixth post, S19 of
the first-principles review, 7 Nov 2026). Every text of the Arabic general edition since 1956 whose signing authority (`Text.authority`,
read from its title) names a minister of education: each minister it names (a joint order names several) becomes a
portfolio, read from «وزير …» up to the first comma, with the person's name in brackets, «بالنيابة», a delegate minister
(«الوزير المنتدب لدى …») and a second office («الناطق الرسمي …») set aside; folded (hamza, final yā, tatweel, the spaces
around «و») so the Bulletin's spellings of one name meet. A portfolio counts when three texts or more carry it; it runs
from the first to the last year one does. Offices, never persons. One query."""
import re
from collections import Counter, defaultdict

from apps.corpus.models import Text
from apps.sources.models import Edition

FOLD = str.maketrans({'ى': 'ي', 'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ـ': None})
EDU = re.compile(r'التربيه|التربية|التعليم|التهذيب')


def portfolios(authority: str) -> list[str]:
    """The education portfolios an authority names, as written (brackets, deputies, delegates and second offices set aside)."""
    a = re.sub(r'\([^)]*\)', '', authority or '')
    out = []
    for part in re.split(r'؛|;|\s+و(?=وزير|الوزير)', a):
        part = re.split(r'[،,]|\s+الناطق الرسمي', part.strip())[0].strip()
        if re.match(r'^(?:الوزير المنتدب|الوزيرة المنتدبة|كاتب الدولة|كاتبة الدولة)', part) or re.search(r'لد[يى] وزير', part):
            continue
        m = re.match(r'^(?:وزير|وزيرة)\s+(?:الدولة\s+)?(.*)$', part)
        if not m:
            continue
        name = re.sub(r'\s+بالنيابة$', '', ' '.join(m.group(1).split()))
        if EDU.search(name) and not name.startswith('المكلف'):
            out.append(name)
    return out


def key(name: str) -> str:
    return re.sub(r'\s+', '', name.translate(FOLD)).replace('ة', 'ه')


def count(meta: dict) -> dict:
    rows = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, first_published_in__date__year__gte=meta['since'],
                                authority__regex=r'التربية|التعليم|التهذيب')
            .values_list('authority', 'first_published_in__date'))
    seen: dict[str, Counter] = defaultdict(Counter)
    years: dict[str, list[int]] = defaultdict(list)
    texts = 0
    for authority, day in rows:
        names = portfolios(authority)
        texts += bool(names)
        for name in names:
            k = key(name)
            seen[k][name] += 1
            years[k].append(day.year)
    names = [{'name': seen[k].most_common(1)[0][0], 'texts': len(years[k]), 'from': min(years[k]), 'to': max(years[k])}
             for k in seen if len(years[k]) >= meta['min_texts']]
    names.sort(key=lambda n: (n['from'], -n['texts']))
    return {'names': names, 'texts': texts, 'longest': max(names, key=lambda n: len(n['name']))['name'] if names else ''}
