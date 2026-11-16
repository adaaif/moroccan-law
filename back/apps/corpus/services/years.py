"""A year of the law: the laws and dahirs signed in it (W8 of the library-search review, 10 Nov 2026). The Bulletin's time
axis led to issues only: 1958 was 54 numbers to open one by one. A year now lists its own texts, the ones other texts
cite most first. Laws, organic laws, decree-laws, constitutions and dahirs only (15,805 on the day it was written);
decrees and orders are counted, and searched. Three queries whatever the year holds."""
from datetime import date

import ma_law
from django.db.models import Count, Q

from apps.corpus.models import Mention, Text
from apps.corpus.services.addresses import text_path
from apps.corpus.services.find import _AMENDS

LISTED = ('law', 'organic_law', 'decree_law', 'constitution', 'dahir')
FIRST = 1912
MOST_CITED = 8
# Texts cited by the hundred because every act of the administration names them: no reader is looking for these.
_ROUTINE = ('بتعيين', 'تفويض')


def year(y: int) -> dict | None:
    """{'year', 'counts': {type: n}, 'texts': [...], 'most_cited': [paths]} or None for a year outside the Bulletin's."""
    from apps.corpus.services.codes import everyday_name
    from apps.corpus.services.titles import subject

    if not FIRST <= y <= date.today().year:
        return None
    counts = dict(Text.objects.filter(signed_on__year=y).values('type').annotate(n=Count('id')).values_list('type', 'n'))
    rows = list(Text.objects.filter(type__in=LISTED)
                .filter(Q(signed_on__year=y) | Q(signed_on__isnull=True, first_published_in__date__year=y))
                .select_related('first_published_in').order_by('signed_on', 'first_published_in__date', 'number', 'id'))
    cited = dict(Mention.objects.filter(to_uri__in=[t.akn_uri for t in rows], state=Mention.State.RESOLVED).values('to_uri')
                 .annotate(n=Count('from_uri', distinct=True)).values_list('to_uri', 'n')) if rows else {}
    texts = []
    for t in rows:
        issue = t.first_published_in
        texts.append({'path': text_path(t.akn_uri), 'type': t.type, 'number': t.number_as_printed, 'name': everyday_name(t), 'subject': subject(t.title_ar),
                      'signed_on': t.signed_on, 'status': t.status, 'cited': cited.get(t.akn_uri, 0),
                      'issue': None if issue is None else {'number': issue.number, 'suffix': issue.suffix, 'key': issue.key},
                      'page': t.first_published_page})
    own = [t for t in rows if cited.get(t.akn_uri, 0) >= 3 and not _AMENDS.search(ma_law.fold(t.title_ar or ''))
           and not any(w in (t.title_ar or '') for w in _ROUTINE)]
    own.sort(key=lambda t: -cited[t.akn_uri])
    return {'year': y, 'counts': counts, 'texts': texts, 'most_cited': [text_path(t.akn_uri) for t in own[:MOST_CITED]]}
