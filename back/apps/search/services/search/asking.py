"""What a query asks besides its words: the words that only ask («واش», «كيفاش», «est-ce que»), set aside before the
words are searched; a constitution named with a year, the one in force that year; a law's number typed the wrong way
round («12.67» for 67.12)."""
import re
from datetime import date

import ma_law

# Words that ask rather than name (row 5 of the reader-experience review), in MSA, Darija and French, with French's small words
# and «au Maroc», which every question about Moroccan law may say (R6 of the road plan): set aside before the words
# are searched, and the words kept are said («بحثنا عن …»). A query of nothing but these is searched whole.
ASKING = frozenset(ma_law.fold(w) for w in """
واش كيفاش كيف شنو شنا اش آش علاش لاش فين أين اين منين شحال كم إمتى امتى متى واقيلا هل ماذا لماذا ما ماهي ماهو هي هو
ديال باش خاصني خصني بغيت نعرف عافاك ممكن يمكن نقدر يقدر عندي
est ce que qu je j peux puis dois doit faut il comment pourquoi quand quel quelle quels quelles combien où une un svp
mon ma mes son sa ses votre vos notre nos le la les l de du des d au aux a à en et ou si on se y est sont faire que qui quoi
المغرب بالمغرب فالمغرب maroc
دابا دبا حاليا daba maintenant actuellement
""".split())


# «دستور 1996», «دستور المملكة المغربية لسنة 1962», «constitution de 1972», with an article or not: the constitution in
# force that year (codes.CODE_BEFORE), never article 1996 of today's (25 Oct 2026: all six, for reference).
CONSTITUTION_YEAR = re.compile(r'(?:(?:ال)?دستور(?:\s+المملكة\s+المغربية)?(?:\s+(?:لسنة|سنة|لعام|عام))?'
                               r'|constitution(?:\s+(?:du\s+maroc|du\s+royaume\s+du\s+maroc|marocaine|de))*)\s+(19[5-9]\d|20[0-4]\d)(?!\d)',
                               re.IGNORECASE)
CITED_ARTICLE = re.compile(r'(?:الفصل|الفصول|فصل|article|art\.)\s*(\d{1,3})(?!\d)', re.IGNORECASE)


def _constitution_of_year(q: str) -> tuple[list[dict], date] | None:
    m = CONSTITUTION_YEAR.search(q)
    if not m:
        return None
    article = CITED_ARTICLE.search(q)
    citation = {'kind': 'article' if article else 'text', 'code': 'constitution', 'raw': m.group(0),
                'article': article.group(1) if article else None}
    return [citation], date(int(m.group(1)), 12, 31)


def _flipped(citation: dict) -> dict | None:
    """The citation with its law's two number groups swapped («12-67» → «67-12»), when it names a law by such a number."""
    groups = (citation.get('text_number') or '').split('-')
    if citation.get('text_kind') in (None, 'law') and len(groups) == 2 and groups[0] != groups[1]:
        return {**citation, 'text_kind': 'law', 'text_number': f'{groups[1]}-{groups[0]}'}
    return None


def asked_words(query: str) -> str:
    """The query without its asking words (the words kept as typed); the query itself when nothing else is left."""
    kept = [w for w in query.split() if not all(t in ASKING for t in ma_law.tokens(w))]
    return ' '.join(kept) if kept else query
