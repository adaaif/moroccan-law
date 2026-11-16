"""The reading model's remarks out of the stored readings and texts (FX5 of the mended-Bulletin review).

    clean_remarks                      what would go, by kind, with examples
    clean_remarks --review FILE        every retry cut (the failed attempt taken with it), before and after, to read
    clean_remarks --write              takes them out of the pages, the published articles, preambles and closings,
                                       then puts the search index right

Readings shown and parsed pass through `clean_reading` already; this cleans what was stored before it knew them. A
run (OcrRun) keeps the reading as the model wrote it."""
import difflib
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.sources.services import remarks

SIEVE = r'[A-Za-z]{3,}|ملاحظة|غير مقروء|غير واضح|تعذر|لم أستطع|نُقل|يُنقل'


class Command(BaseCommand):
    help = "Take the reading model's remarks out of stored pages and texts (a dry run unless --write)."

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')
        parser.add_argument('--review', help='write every retry cut, before and after, to this file')

    def handle(self, *args, write: bool, review: str | None = None, **opts):
        from apps.corpus.models import Article, Text, Version
        from apps.corpus.services import generation
        from apps.search.services.index import rebuild
        from apps.sources.models import Page

        kinds, notes = Counter(), []
        changed_pages, changed_articles, changed_versions, texts = [], [], [], set()

        def clean(value: str, where: str) -> str:
            c = Counter()
            out = remarks.strip(value, c)
            kinds.update(c)
            if c.get('retry') and review:
                gone = [ln for ln in difflib.unified_diff(value.split('\n'), out.split('\n'), lineterm='', n=0)
                        if ln.startswith('-') and not ln.startswith('---')]
                notes.append(f'=== {where}: {len(value)} → {len(out)} letters\n' + '\n'.join(g[:240] for g in gone))
            return out

        for page in Page.objects.filter(text__regex=SIEVE).select_related('document__issue').iterator(chunk_size=500):
            issue = getattr(page.document, 'issue', None)
            new = clean(page.text, f'{issue.edition} {issue.key} p.{page.index}' if issue else f'page {page.pk}')
            if new != page.text.strip():
                page.text = new
                changed_pages.append(page)
        arts = Article.objects.filter(body__regex=SIEVE, version__consolidation__in=('as_published', 'translation')
                                      ).select_related('version__text')
        for a in arts.iterator(chunk_size=500):
            new = clean(a.body, f'{a.version.text.akn_uri}#{a.eid}')
            if new != a.body.strip():
                a.body = new
                changed_articles.append(a)
                texts.add(a.version.text_id)
        vers = Version.objects.filter(Q(preamble__regex=SIEVE) | Q(closing__regex=SIEVE),
                                      consolidation__in=('as_published', 'translation')).select_related('text')
        for v in vers.iterator(chunk_size=500):
            preamble, closing = clean(v.preamble, f'{v.text.akn_uri} preamble'), clean(v.closing, f'{v.text.akn_uri} closing')
            if preamble != v.preamble.strip() or closing != v.closing.strip():
                v.preamble, v.closing = preamble, closing
                changed_versions.append(v)
                texts.add(v.text_id)
        self.stdout.write(f'{len(changed_pages)} pages, {len(changed_articles)} articles, {len(changed_versions)} '
                          f'preambles or closings; by kind: ' + ', '.join(f'{k} {n}' for k, n in kinds.most_common()))
        if review:
            Path(review).write_text('\n\n'.join(notes), encoding='utf-8')
            self.stdout.write(f'{len(notes)} retry cuts written to {review}')
        if write:
            Page.objects.bulk_update(changed_pages, ['text'], batch_size=500)
            Article.objects.bulk_update(changed_articles, ['body'], batch_size=500)
            Version.objects.bulk_update(changed_versions, ['preamble', 'closing'], batch_size=500)
            rebuild(list(Text.objects.filter(pk__in=texts)), log=self.stdout.write)
            generation.bump('corpus')
