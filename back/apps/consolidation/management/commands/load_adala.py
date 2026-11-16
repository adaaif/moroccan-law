"""Texts from Adala, the Ministry of Justice's portal, into the corpus (row 3: filling the shelf): each registered
PDF read from its text layer (services/adala.py) into a version of its text — «consolidated by Adala, for
information; the BO prevails» — dated by Adala's own «صيغة محينة بتاريخ …». Its footnotes are kept on the
document, each with the article that marks it, and those that name the text that changed an article become that
article's history (Change, source «adala»): one more witness beside the SGG's notes (row L9).

    load_adala samples/adala/adala_118.pdf          # the family code, law 70.03
    load_adala samples/adala/adala_89.pdf           # the penal code, approved by dahir 1.59.413

The text is the one whose number the title gives («القانون رقم 70.03 …»); one the corpus does not hold yet is
created. Run again, a file replaces its own version.
"""
import re
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.consolidation.models import Change
from apps.consolidation.services import adala, sgg
from apps.consolidation.services.instructions.labels import label_key
from apps.consolidation.services.versions import save_version, text_at, text_for
from apps.corpus.models import Consolidation
from apps.corpus.services import works
from apps.sources.models import Document, Source
from apps.sources.services.ingest import corpus_path

NUMBER = re.compile(r'رقم\s+(\d+(?:\.\d+)+)')


class Command(BaseCommand):
    help = "Load Adala's consolidated texts as versions, their footnotes kept."

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+', help='the documents\' paths under CORPUS_DIR')
        parser.add_argument('--article-word', choices=['المادة', 'الفصل'],
                            help='the word that numbers this text\'s own articles, when it quotes another text\'s')
        parser.add_argument('--as-of', help='for a copy whose cover gives no «صيغة محينة بتاريخ»: the date it stands at '
                                            '(the BO of the text, or of the last change it holds), YYYY-MM-DD')
        parser.add_argument('--uri', help='for a text whose title gives no number (the DOC, the land-registration '
                                          'dahir of 1913): its address, e.g. /akn/ma/act/code/doc')

    def handle(self, *args, paths, as_of=None, article_word=None, uri=None, **opts):
        for path in paths:
            doc = Document.objects.filter(source=Source.ADALA, path=path).first()
            if doc is None:
                raise CommandError(f'{path}: no Adala document at this path')
            read = adala.read(str(corpus_path(doc)), article_word)
            text = read.text
            sgg.page_tables(Path(path).stem, text.articles)      # what the session read on the page images
            if text.as_of is None and as_of:
                text.as_of = date.fromisoformat(as_of)
            m = NUMBER.search(text.title)
            if not text.articles or not (m or uri) or not text.as_of:
                raise CommandError(f'{path}: not read whole (articles {len(text.articles)}, title «{text.title}», '
                                   f'date {text.as_of})')
            with transaction.atomic():
                if uri:
                    found, created = text_at(uri, text.title)
                else:
                    found, created = text_for(m.group(1).replace('.', '-'), text.title, Consolidation.ADALA)
                doc.meta = {**doc.meta, 'as_of': text.as_of.isoformat(), 'first_issue': text.first_issue,
                            'first_page': text.first_page, 'layer': text.stats,
                            'footnotes': [{'number': f.number, 'page': f.page, 'article': f.article, 'text': f.text}
                                          for f in read.footnotes]}
                doc.save(update_fields=['meta'])
                rows = save_version(found, Consolidation.ADALA, doc, text.as_of, text.articles, read.preamble)
                Change.objects.filter(text_uri=found.akn_uri, source=Change.Source.ADALA).delete()
                notes = []
                for f in read.footnotes:
                    if not f.article:
                        continue
                    for n in adala.footnote_changes(f.text):
                        by, _ = works.resolve(n['kind'], n['number'])
                        notes.append(Change(text_uri=found.akn_uri, number=label_key(f.article), verb=n['verb'],
                                            source=Change.Source.ADALA, by_kind=n['kind'],
                                            by_number=works.fold(n['number']), by_uri=by, issue=n['issue'],
                                            issue_bis=n['bis'], page=n['page']))
                Change.objects.bulk_create(notes)
            self.stdout.write(f'{path}: {len(rows)} articles, {len(read.footnotes)} footnotes ({len(notes)} changes), '
                              f'as of {text.as_of}, '
                              f'{text.stats["unknown"]}/{text.stats["words"]} words unknown  {found.akn_uri}'
                              + ('  (new text)' if created else ''))
