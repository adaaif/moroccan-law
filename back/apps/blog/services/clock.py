"""Morocco's legal time, text by text, for «من غرينيتش إلى غرينيتش» (the blog's thirteenth post, S6 of
the first-principles review, 6 Nov 2026). The moves of the clock are the meta's, read in each text's articles on its printed page; what is
counted here ties each text to its issue (its day), its printed page (the page viewer's address) and, when the site has cut
it, its own address; and it reads the first day of Ramadan and of Shawwal each year from the Bulletin's own Hijri dates
(its mastheads and the running heads of its first pages), since no text on the clock names Ramadan. Four queries."""
import re
from collections import Counter, defaultdict
from datetime import date, timedelta

from django.db.models import Q

from apps.corpus.models import Text
from apps.corpus.services.addresses import text_path
from apps.sources.models import Issue, Page

# «4 رمضان 1428 (17 سبتمبر 2007)», «فاتح رمضان 1447»: a day of a Hijri month as an issue prints it.
HIJRI_DAY = re.compile(r'(\d{1,2}|فاتح)\s*(?:من\s*)?(رمضان|شوال)\s*(14\d\d)')
# A running head: «عدد 7279 - 23 شعبان 1445 (4 مارس 2024)».
HEAD = re.compile(r'عدد\s*\d+[^()]{0,25}?(?:\d{1,2}|فاتح)\s*(?:من\s*)?(?:رمضان|شوال)\s*14\d\d')


def _key(edition: str, number: int, bis: bool) -> tuple[str, int, str]:
    return edition, int(number), 'bis' if bis else ''


def _months(rows) -> dict[str, dict[str, str]]:
    """The first day of each month a year, as most of that year's issues reckon it (one stray reading is outvoted)."""
    votes: dict[tuple[str, int], Counter] = defaultdict(Counter)
    for day, hijri in rows:
        for m in HIJRI_DAY.finditer(hijri or ''):
            n = 1 if m.group(1) == 'فاتح' else int(m.group(1))
            if n > 30:
                continue
            first = day - timedelta(days=n - 1)
            month = 'ramadan' if m.group(2) == 'رمضان' else 'shawwal'
            votes[(month, first.year)][first] += 1
            break
    out: dict[str, dict[str, str]] = {'ramadan': {}, 'shawwal': {}}
    for (month, year), c in sorted(votes.items()):
        out[month][str(year)] = c.most_common(1)[0][0].isoformat()
    return out


def tie(texts: list[dict]) -> dict:
    """Each text's issue (its day), its printed page's viewer address and, when the site has cut it, its own address: a
    text is {key, edition, issue, bis?, page, index?, akn?, also?}. Three queries, whatever the number of texts."""
    keys = {_key(t['edition'], t['issue'], t.get('bis', False)) for t in texts}
    keys |= {_key(t['also']['edition'], t['also']['issue'], False) for t in texts if t.get('also')}
    where = Q()
    for edition, number, suffix in keys:
        where |= Q(edition=edition, number=number, suffix=suffix)
    issues = {(i.edition, i.number, i.suffix): i for i in Issue.objects.filter(where)}
    pages = {}
    wanted = Q()
    for t in texts:
        for edition, number, bis, printed, index in ((t['edition'], t['issue'], t.get('bis', False), t.get('page'), t.get('index')),
                                                     *(((t['also']['edition'], t['also']['issue'], False, t['also'].get('page'), None),) if t.get('also') else ())):
            issue = issues.get(_key(edition, number, bis))
            if issue is None or issue.document_id is None:
                continue
            wanted |= Q(document_id=issue.document_id, index=index) if index is not None else Q(document_id=issue.document_id, printed_number=printed)
    for p in Page.objects.filter(wanted).values('document_id', 'index', 'printed_number'):
        pages[(p['document_id'], p['printed_number'])] = p['index']
        pages[(p['document_id'], ('index', p['index']))] = p['index']
    cut = set(Text.objects.filter(akn_uri__in=[t['akn'] for t in texts if t.get('akn')]).values_list('akn_uri', flat=True))

    def where_printed(edition, number, bis, printed, index):
        issue = issues.get(_key(edition, number, bis))
        if issue is None:
            return None
        found = pages.get((issue.document_id, ('index', index) if index is not None else printed))
        return {'issue': f"{issue.number}{' bis' if issue.suffix else ''}", 'edition': issue.edition, 'published': issue.date.isoformat(),
                'page': printed, 'viewer': f'/pages/{issue.document_id}/{found}' if found is not None else None}

    out = {}
    for t in texts:
        first = where_printed(t['edition'], t['issue'], t.get('bis', False), t.get('page'), t.get('index'))
        also = where_printed(t['also']['edition'], t['also']['issue'], False, t['also'].get('page'), None) if t.get('also') else None
        out[t['key']] = {**(first or {}), 'path': text_path(t['akn']) if t.get('akn') in cut else None,
                         **({'also': also} if also else {})}
    return out


def count(meta: dict) -> dict:
    out = tie(meta['texts'])
    # The Bulletin's own Hijri dates, 2007–2026: the mastheads the site keeps, and the running heads of the first pages.
    span = (date(2007, 1, 1), date(2026, 12, 31))
    rows = list(Issue.objects.filter(edition='general_ar', date__range=span, hijri_date__regex='(رمضان|شوال)')
                .values_list('date', 'hijri_date'))
    heads = (Page.objects.filter(document__issue__edition='general_ar', document__issue__date__range=span, index__lt=3,
                                 text__regex='(رمضان|شوال) *14[0-9][0-9]')
             .values_list('document__issue__date', 'text'))
    rows += [(day, m.group(0)) for day, body in heads for m in [HEAD.search(body or '')] if m]
    return {'texts': out, 'hijri': _months(rows)}
