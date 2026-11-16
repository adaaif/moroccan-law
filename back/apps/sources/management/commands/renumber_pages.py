"""Printed page numbers put right (FX4 of the mended-Bulletin review).

    renumber_pages              what would change: issues left at page 1 mid-year, texts whose first page is off
    renumber_pages --write      numbers the sure ones, reads a page or two of the others with Tesseract and numbers
                                those whose pages print the start; then puts each text's first page where its pages
                                begin, and the search index right
"""
from django.core.management.base import BaseCommand

from apps.sources.services import pages


class Command(BaseCommand):
    help = "Put printed page numbers right from the issues around and the pages themselves (a dry run unless --write)."

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')
        parser.add_argument('--files', action='store_true', help="move the issues' texts.json and toc.json too")

    def handle(self, *args, write: bool, files: bool = False, **opts):
        from apps.corpus.models import Text
        from apps.corpus.services import generation
        from apps.search.services.index import rebuild

        found = pages.misnumbered()
        sure = [p for p in found if p.sure]
        self.stdout.write(f'{len(found)} issues left at page 1 mid-year: {len(sure)} sure from their neighbours, '
                          f'{len(found) - len(sure)} to read on the page')
        touched = []
        for p in found:
            ok = p.sure or (write and pages.confirm(p))
            tag = 'sure' if p.sure else ('confirmed' if ok else 'left')
            line = f'  {p.issue.edition} {p.issue.key} ({p.issue.date}, {p.pages} pages): 1 → {p.start} [{tag}]'
            if p.evidence:
                line += ' ' + '; '.join(p.evidence)
            if write and ok:
                done = pages.renumber(p.issue, p.start, files=files)
                touched.append(p.issue.pk)
                line += f' — {done["texts"]} texts, {done["articles"]} articles moved'
            self.stdout.write(line)
        off = pages.text_pages(write=write)
        self.stdout.write(f'{len(off)} texts whose first page is not where their pages begin'
                          + (' — put right' if write else ''))
        for uri, was, first in off[:10]:
            self.stdout.write(f'  {uri}: {was} → {first}')
        if write:
            ids = set(touched) | set(Text.objects.filter(akn_uri__in=[u for u, _, _ in off]).values_list(
                'first_published_in', flat=True))
            rebuild(list(Text.objects.filter(first_published_in__in=ids)), log=self.stdout.write)
            generation.bump('corpus')
