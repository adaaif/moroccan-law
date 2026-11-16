"""The few rows a counting service's test needs: an issue with its file, a page of it, a text, a version with its
articles. Each test builds the smallest corpus that shows its rule, rows on both sides of it."""
from datetime import date
from itertools import count

from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Status, Text, Version
from apps.sources.models import Document, Edition, Issue, Page

_files = count(1)


def issue(number, day, *, suffix='', edition=Edition.GENERAL_AR, pages=1, first_page=None, hijri='', copy_of=None):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{next(_files):064d}', path=f'BO_{number}{suffix}_{edition}.pdf',
                                  mime='application/pdf', language='fr' if edition == Edition.TRANSLATION_FR else 'ar', bytes=1,
                                  fetched_at=timezone.now(), page_count=pages)
    return Issue.objects.create(edition=edition, number=number, suffix=suffix, date=day, document=doc, first_page_number=first_page,
                                hijri_date=hijri, copy_of=copy_of)


def page(of, index, printed=None, body=''):
    return Page.objects.create(document=of.document, index=index, kind='scan', printed_number=printed, text=body)


def text(akn, kind, published_in=None, *, title='', page=None, status=Status.IN_FORCE, **fields):
    return Text.objects.create(akn_uri=akn, type=kind, title_ar=title, first_published_in=published_in, first_published_page=page,
                               status=status, **fields)


def version(of, *bodies, consolidation=Consolidation.AS_PUBLISHED, language='ar', valid_from=None, closing=''):
    """A version whose articles are `bodies` in order, art_1, art_2…; a body given as (eid, body) is that article."""
    day = valid_from or (of.first_published_in.date if of.first_published_in_id else date(2000, 1, 1))
    v = Version.objects.create(text=of, language=language, valid_from=day, consolidation=consolidation, closing=closing)
    for k, b in enumerate(bodies, 1):
        eid, body = b if isinstance(b, tuple) else (f'art_{k}', b)
        article(v, k, eid, body)
    return v


def article(of, order, eid, body, printed_page=None):
    return Article.objects.create(version=of, order=order, label=eid, number=eid.removeprefix('art_'), eid=eid, body=body,
                                  printed_page=printed_page)
