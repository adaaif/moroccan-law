"""The SGG's consolidated texts into the corpus (row 19): each fetched PDF (fetch_sgg_consolidated) read from its
repaired text layer into a version of its text — «consolidated by the SGG, for information; the BO prevails» —
dated by the last change it carries, and each article's notes into its history (Change, source «sgg»):

    load_sgg_consolidated               # every registered SGG text
    load_sgg_consolidated --only 2_00

A text the corpus does not hold yet is created; a waiting text's title becomes the SGG's. Run again, it replaces its own
versions and notes."""
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.consolidation.models import Change
from apps.consolidation.services import sgg
from apps.consolidation.services.instructions.labels import label_key
from apps.consolidation.services.versions import save_version, text_for
from apps.corpus.models import Consolidation
from apps.corpus.services import works
from apps.sources.models import Document, Source


NUMBER = re.compile(r'رقم\s+(\d+(?:\.\d+)+)')


def _same(a: str, b: str) -> bool:
    """«17.04» and «17-04», «01.09» and «1-09»: one number however printed."""
    parts = lambda n: [p.lstrip('0') or '0' for p in re.split(r'[.\-]', n)]
    return parts(a) == parts(b)


def title_of(read: str, listed: str, number: str) -> str:
    """The title the file's layer gives, unless it names no number or another one than the file's: 17_04.pdf's
    layer reads «القانون رقم 17.0 …», 131_13.pdf's gives none. The SGG's list names every file, so its title stands
    in then."""
    m = NUMBER.search(read)
    return read if m and _same(m.group(1), number) else listed or read


class Command(BaseCommand):
    help = "Load the SGG's consolidated texts as versions with their articles' histories."

    def add_arguments(self, parser):
        parser.add_argument('--only', nargs='*', default=[])

    def handle(self, *args, only, **opts):
        docs = Document.objects.filter(source=Source.SGG_CONSOLIDATED).order_by('id')
        totals = {'texts': 0, 'articles': 0, 'notes': 0, 'created': 0}
        for doc in docs:
            stem = doc.url.rsplit('/', 1)[-1].removesuffix('.pdf').removesuffix('_ar')
            if only and stem not in only:
                continue
            read = sgg.read([p.layer_text for p in doc.pages.order_by('index')])
            sgg.page_tables(stem, read.articles)
            if not read.articles:
                self.stderr.write(f'{stem}: no articles read')
                continue
            number = stem.replace('_', '-')
            with transaction.atomic():
                read.title = title_of(read.title, doc.title, number)
                text, created = text_for(number, read.title, Consolidation.SGG)
                totals['created'] += created
                dates = [n.on for a in read.articles for n in a.notes if n.on and (not read.as_of or n.on <= read.as_of)]
                valid_from = max(dates) if dates else read.as_of
                doc.meta = {**doc.meta, 'stem': stem, 'as_of': read.as_of.isoformat() if read.as_of else None,
                            'first_issue': read.first_issue, 'first_page': read.first_page, 'layer': read.stats}
                doc.save(update_fields=['meta'])
                rows = save_version(text, Consolidation.SGG, doc, valid_from, read.articles)
                Change.objects.filter(text_uri=text.akn_uri, source=Change.Source.SGG).delete()
                changes = []
                for a in read.articles:
                    key = label_key(a.label) or a.number
                    for n in a.notes:
                        by, _ = works.resolve(n.kind, n.number)
                        changes.append(Change(text_uri=text.akn_uri, number=key, verb=n.verb, source=Change.Source.SGG,
                                              by_kind=n.kind, by_number=works.fold(n.number), by_uri=by,
                                              by_article=n.article, issue=n.issue, issue_bis=n.issue_bis, page=n.page,
                                              published_on=n.on))
                Change.objects.bulk_create(changes)
            totals['texts'] += 1
            totals['articles'] += len(rows)
            totals['notes'] += len(changes)
            self.stdout.write(f'{stem:>12}  {len(rows):>4} articles  {len(changes):>3} notes  from {valid_from}  '
                              f'{read.stats["unknown"]}/{read.stats["words"]} words unknown  {text.akn_uri}')
        self.stdout.write(f'{totals}')
